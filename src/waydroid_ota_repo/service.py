from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .manifest import (
    dump_json_payload,
    dump_manifest,
    dump_release_index,
    load_manifest,
    load_release_index,
)
from .models import (
    Artifact,
    ConvertConfig,
    Publisher,
    RawProxyRootPublisher,
    ReleaseIndex,
    ReleaseMetadata,
    ReleasePlan,
    UpstreamManifest,
)
from .render import (
    build_raw_proxy_channel_plan,
    build_release_plan,
    classify_artifact_role,
    render_latest_artifacts_dir,
    rewrite_manifest,
)
from .storage import Downloader, HttpDownloader, ensure_artifact_cached


@dataclass(frozen=True, slots=True)
class ConversionResult:
    manifest_path: Path
    latest_manifest_path: Path
    release_index_path: Path
    latest_index_path: Path
    artifact_paths: tuple[Path, ...]


def convert(
    config: ConvertConfig, downloader: Downloader | None = None
) -> ConversionResult:
    manifest = load_manifest(config.upstream_manifest)
    active_downloader = downloader if downloader is not None else HttpDownloader()
    artifacts = tuple(
        ensure_artifact_cached(
            artifact=artifact,
            cache_dir=config.cache_dir,
            downloader=active_downloader,
        )
        for artifact in manifest.artifacts
    )
    rewritten = rewrite_manifest(manifest, config.publisher)
    _ = config.dist_dir.mkdir(parents=True, exist_ok=True)
    release_plan = build_release_plan(
        dist_dir=config.dist_dir,
        version=manifest.version,
        publisher=config.publisher,
    )
    dump_manifest(rewritten, release_plan.versioned_manifest_path)
    dump_manifest(rewritten, release_plan.latest_manifest_path)
    publish_artifacts(
        artifact_paths=artifacts,
        dist_dir=config.dist_dir,
        version=manifest.version,
    )
    publish_raw_proxy_root_outputs(
        manifest=manifest,
        artifact_paths=artifacts,
        publisher=config.publisher,
        dist_dir=config.dist_dir,
    )
    release_index = update_release_index(release_plan=release_plan)
    dump_release_index(release_index, release_plan.release_index_path)
    dump_release_index(release_index, release_plan.latest_index_path)
    return ConversionResult(
        manifest_path=release_plan.versioned_manifest_path,
        latest_manifest_path=release_plan.latest_manifest_path,
        release_index_path=release_plan.release_index_path,
        latest_index_path=release_plan.latest_index_path,
        artifact_paths=artifacts,
    )


def publish_artifacts(
    *, artifact_paths: tuple[Path, ...], dist_dir: Path, version: str
) -> None:
    versioned_target_dir = dist_dir / "releases" / version / "artifacts"
    latest_target_dir = render_latest_artifacts_dir(dist_dir)
    _ = versioned_target_dir.mkdir(parents=True, exist_ok=True)
    _ = latest_target_dir.mkdir(parents=True, exist_ok=True)
    for artifact_path in artifact_paths:
        content = artifact_path.read_bytes()
        _ = (versioned_target_dir / artifact_path.name).write_bytes(content)
        _ = (latest_target_dir / artifact_path.name).write_bytes(content)


def update_release_index(*, release_plan: ReleasePlan) -> ReleaseIndex:
    existing_index = load_release_index(release_plan.release_index_path)
    existing_releases = () if existing_index is None else existing_index.releases
    current_release = ReleaseMetadata(
        version=release_plan.version,
        manifest_url=release_plan.versioned_manifest_url,
    )
    preserved_releases = tuple(
        release
        for release in existing_releases
        if release.version != release_plan.version
    )
    releases = tuple(
        sorted(
            (*preserved_releases, current_release),
            key=lambda release: release.version,
        )
    )
    return ReleaseIndex(
        latest_version=release_plan.version,
        latest_manifest_url=release_plan.latest_manifest_url,
        releases=releases,
    )


def publish_raw_proxy_root_outputs(
    *,
    manifest: UpstreamManifest,
    artifact_paths: tuple[Path, ...],
    publisher: Publisher,
    dist_dir: Path,
) -> None:
    match publisher:
        case RawProxyRootPublisher() as raw_proxy_root_publisher:
            _publish_raw_proxy_root_outputs(
                manifest=manifest,
                artifact_paths=artifact_paths,
                publisher=raw_proxy_root_publisher,
                dist_dir=dist_dir,
            )
        case _:
            return


def _publish_raw_proxy_root_outputs(
    *,
    manifest: UpstreamManifest,
    artifact_paths: tuple[Path, ...],
    publisher: RawProxyRootPublisher,
    dist_dir: Path,
) -> None:
    artifact_path_by_name = {
        artifact_path.name: artifact_path for artifact_path in artifact_paths
    }
    channel = manifest.channel or "stable"
    for role in ("system", "vendor"):
        role_artifacts = tuple(
            artifact
            for artifact in manifest.artifacts
            if classify_artifact_role(artifact) == role
        )
        if len(role_artifacts) == 0:
            continue
        channel_plan = build_raw_proxy_channel_plan(
            dist_dir=dist_dir,
            role=role,
            channel=channel,
            version=manifest.version,
            publisher=publisher,
        )
        _ = channel_plan.artifacts_dir.mkdir(parents=True, exist_ok=True)
        for artifact in role_artifacts:
            source_path = artifact_path_by_name[artifact.name]
            _ = (channel_plan.artifacts_dir / artifact.name).write_bytes(
                source_path.read_bytes()
            )
        payload = build_waydroid_response_payload(
            artifacts=role_artifacts,
            role=role,
            channel=channel,
            version=manifest.version,
            artifact_base_url=channel_plan.artifact_base_url,
        )
        dump_json_payload(
            payload=payload,
            path=channel_plan.latest_channel_manifest_path,
        )
        dump_json_payload(
            payload=payload,
            path=channel_plan.latest_alias_manifest_path,
        )
        dump_json_payload(
            payload=payload,
            path=channel_plan.versioned_manifest_path,
        )


def build_waydroid_response_payload(
    *,
    artifacts: tuple[Artifact, ...],
    role: Literal["system", "vendor"],
    channel: str,
    version: str,
    artifact_base_url: str,
) -> dict[str, object]:
    response: list[dict[str, object]] = []
    artifact: Artifact
    for artifact in artifacts:
        item = artifact.model_dump(mode="python")
        item["filename"] = artifact.name
        item["id"] = artifact.sha256
        item["romtype"] = channel
        item["version"] = version
        item["url"] = f"{artifact_base_url.rstrip('/')}/{artifact.name}"
        response.append(item)
    return {
        "response": response,
        "role": role,
        "channel": channel,
        "version": version,
    }
