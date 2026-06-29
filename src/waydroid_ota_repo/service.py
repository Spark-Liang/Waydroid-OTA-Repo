from dataclasses import dataclass
from pathlib import Path

from .manifest import (
    dump_manifest,
    dump_release_index,
    load_manifest,
    load_release_index,
)
from .models import ConvertConfig, ReleaseIndex, ReleaseMetadata, ReleasePlan
from .render import (
    build_release_plan,
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
