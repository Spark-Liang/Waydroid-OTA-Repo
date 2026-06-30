import shutil
from pathlib import Path
from typing import Literal

from httpx2 import HTTPError

from .errors import UpstreamFetchError
from .http import create_client
from .manifest import load_manifest_text
from .models import (
    Artifact,
    RemoteArtifact,
    RemoteOtaManifestSource,
    RemoteOtaSourceSet,
    UpstreamManifest,
)
from .render import classify_artifact_role


def fetch_upstream_manifest_set(upstream: RemoteOtaSourceSet) -> UpstreamManifest:
    system_source = upstream.system
    vendor_source = upstream.vendor
    return _merge_partition_manifests(
        system_manifest=_fetch_remote_manifest(system_source),
        vendor_manifest=_fetch_remote_manifest(vendor_source),
    )


def publish_artifact_copy(*, artifact_path: Path, target_path: Path) -> None:
    _ = target_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        artifact_path.open("rb") as source_handle,
        target_path.open("wb") as target_handle,
    ):
        _ = shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)


def _fetch_remote_manifest(source: RemoteOtaManifestSource) -> UpstreamManifest:
    with create_client() as client:
        try:
            response = client.get(str(source.manifest_url))
            _ = response.raise_for_status()
        except HTTPError as exc:
            raise UpstreamFetchError(
                url=str(source.manifest_url),
                reason=str(exc),
            ) from exc
    manifest = load_manifest_text(response.text)
    _validate_remote_artifact_urls(manifest)
    return manifest


def _validate_remote_artifact_urls(manifest: UpstreamManifest) -> None:
    for artifact in manifest.artifacts:
        _ = RemoteArtifact(name=artifact.name, url=artifact.url)


def _merge_partition_manifests(
    *, system_manifest: UpstreamManifest, vendor_manifest: UpstreamManifest
) -> UpstreamManifest:
    if system_manifest.version != vendor_manifest.version:
        raise UpstreamFetchError(
            url=str(system_manifest.artifacts[0].url),
            reason=(
                "system/vendor manifest versions differ: "
                f"{system_manifest.version} != {vendor_manifest.version}"
            ),
        )
    system_artifact = _extract_partition_artifact(
        system_manifest,
        expected_role="system",
    )
    vendor_artifact = _extract_partition_artifact(
        vendor_manifest,
        expected_role="vendor",
    )
    return UpstreamManifest(
        version=system_manifest.version,
        channel=system_manifest.channel or "stable",
        artifacts=(system_artifact, vendor_artifact),
        response=(system_artifact, vendor_artifact),
    )


def _extract_partition_artifact(
    manifest: UpstreamManifest, *, expected_role: Literal["system", "vendor"]
) -> Artifact:
    matching_artifacts = tuple(
        artifact
        for artifact in manifest.artifacts
        if classify_artifact_role(artifact) == expected_role
    )
    if len(matching_artifacts) == 0:
        raise UpstreamFetchError(
            url=str(manifest.artifacts[0].url),
            reason=(
                f"expected at least one {expected_role} artifact, got 0"
            ),
        )
    return max(matching_artifacts, key=_artifact_datetime)


def _artifact_datetime(artifact: Artifact) -> int:
    payload = artifact.model_dump(mode="python")
    raw_datetime = payload.get("datetime")
    return raw_datetime if isinstance(raw_datetime, int) else 0
