from pathlib import Path
from urllib.parse import quote

from .models import (
    Artifact,
    GitHubPublisher,
    LocalPublisher,
    NexusRawPublisher,
    Publisher,
    ReleasePlan,
    UpstreamManifest,
)


def rewrite_manifest(
    manifest: UpstreamManifest, publisher: Publisher
) -> UpstreamManifest:
    artifacts = tuple(
        rewrite_artifact(artifact, publisher) for artifact in manifest.artifacts
    )
    response = None
    if manifest.response is not None:
        response = tuple(
            rewrite_artifact(artifact, publisher) for artifact in manifest.response
        )
    return manifest.model_copy(
        update={
            "artifacts": artifacts,
            "response": response,
        }
    )


def rewrite_artifact(artifact: Artifact, publisher: Publisher) -> Artifact:
    rewritten_url = render_artifact_url(artifact=artifact, publisher=publisher)
    payload = artifact.model_dump(mode="python")
    payload["url"] = rewritten_url
    return Artifact.model_validate(payload)


def render_artifact_url(*, artifact: Artifact, publisher: Publisher) -> str:
    match publisher:
        case LocalPublisher(base_path=base_path):
            return (render_latest_artifacts_dir(base_path) / artifact.name).as_posix()
        case GitHubPublisher(
            owner=owner,
            repo=repo,
            release_tag=release_tag,
            use_releases_for_artifacts=True,
        ):
            return (
                f"https://github.com/{owner}/{repo}/releases/download/"
                f"{release_tag}/{artifact.name}"
            )
        case GitHubPublisher(owner=owner, repo=repo, pages_prefix=pages_prefix):
            prefix = pages_prefix.strip("/")
            return (
                f"https://{owner}.github.io/{repo}/{prefix}/latest/artifacts/{artifact.name}"
            )
        case NexusRawPublisher(
            base_url=base_url,
            repository=repository,
            directory_prefix=directory_prefix,
        ):
            normalized_base = base_url.rstrip("/")
            prefix = directory_prefix.strip("/")
            quoted_name = quote(artifact.name)
            return (
                f"{normalized_base}/repository/{repository}/{prefix}/latest/artifacts/{quoted_name}"
            )


def build_release_plan(
    *, dist_dir: Path, version: str, publisher: Publisher
) -> ReleasePlan:
    versioned_manifest_path = render_versioned_manifest_path(
        dist_dir=dist_dir,
        version=version,
    )
    latest_manifest_path = render_manifest_path(dist_dir)
    release_index_path = render_release_index_path(dist_dir)
    latest_index_path = render_latest_index_path(dist_dir)
    versioned_artifacts_dir = render_versioned_artifacts_dir(
        dist_dir=dist_dir,
        version=version,
    )
    latest_artifacts_dir = render_latest_artifacts_dir(dist_dir)
    versioned_manifest_url = render_manifest_url_for_version(
        publisher=publisher,
        version=version,
    )
    latest_manifest_url = render_latest_manifest_url(publisher=publisher)
    release_index_url = render_release_index_url(publisher=publisher)
    return ReleasePlan(
        version=version,
        versioned_manifest_path=versioned_manifest_path,
        latest_manifest_path=latest_manifest_path,
        release_index_path=release_index_path,
        latest_index_path=latest_index_path,
        versioned_artifacts_dir=versioned_artifacts_dir,
        latest_artifacts_dir=latest_artifacts_dir,
        versioned_manifest_url=versioned_manifest_url,
        latest_manifest_url=latest_manifest_url,
        release_index_url=release_index_url,
    )


def render_manifest_path(dist_dir: Path) -> Path:
    return dist_dir / "manifest.json"


def render_versioned_manifest_path(*, dist_dir: Path, version: str) -> Path:
    return dist_dir / "releases" / version / "manifest.json"


def render_release_index_path(dist_dir: Path) -> Path:
    return dist_dir / "releases" / "index.json"


def render_latest_index_path(dist_dir: Path) -> Path:
    return dist_dir / "latest.json"


def render_versioned_artifacts_dir(*, dist_dir: Path, version: str) -> Path:
    return dist_dir / "releases" / version / "artifacts"


def render_latest_artifacts_dir(base_path: Path) -> Path:
    return base_path / "latest" / "artifacts"


def render_latest_manifest_url(*, publisher: Publisher) -> str:
    match publisher:
        case LocalPublisher(base_path=base_path):
            return render_manifest_path(base_path).as_posix()
        case GitHubPublisher(owner=owner, repo=repo, pages_prefix=pages_prefix):
            prefix = pages_prefix.strip("/")
            return f"https://{owner}.github.io/{repo}/{prefix}/manifest.json"
        case NexusRawPublisher(
            base_url=base_url,
            repository=repository,
            directory_prefix=directory_prefix,
        ):
            return _render_nexus_url(
                base_url=base_url,
                repository=repository,
                directory_prefix=directory_prefix,
                relative_path="manifest.json",
            )


def render_manifest_url_for_version(*, publisher: Publisher, version: str) -> str:
    match publisher:
        case LocalPublisher(base_path=base_path):
            return render_versioned_manifest_path(
                dist_dir=base_path,
                version=version,
            ).as_posix()
        case GitHubPublisher(owner=owner, repo=repo, pages_prefix=pages_prefix):
            prefix = pages_prefix.strip("/")
            return (
                f"https://{owner}.github.io/{repo}/{prefix}/releases/"
                f"{quote(version)}/manifest.json"
            )
        case NexusRawPublisher(
            base_url=base_url,
            repository=repository,
            directory_prefix=directory_prefix,
        ):
            return _render_nexus_url(
                base_url=base_url,
                repository=repository,
                directory_prefix=directory_prefix,
                relative_path=f"releases/{quote(version)}/manifest.json",
            )


def render_release_index_url(*, publisher: Publisher) -> str:
    match publisher:
        case LocalPublisher(base_path=base_path):
            return render_release_index_path(base_path).as_posix()
        case GitHubPublisher(owner=owner, repo=repo, pages_prefix=pages_prefix):
            prefix = pages_prefix.strip("/")
            return f"https://{owner}.github.io/{repo}/{prefix}/releases/index.json"
        case NexusRawPublisher(
            base_url=base_url,
            repository=repository,
            directory_prefix=directory_prefix,
        ):
            return _render_nexus_url(
                base_url=base_url,
                repository=repository,
                directory_prefix=directory_prefix,
                relative_path="releases/index.json",
            )


def _render_nexus_url(
    *,
    base_url: str,
    repository: str,
    directory_prefix: str,
    relative_path: str,
) -> str:
    normalized_base = base_url.rstrip("/")
    prefix = directory_prefix.strip("/")
    return (
        f"{normalized_base}/repository/{repository}/{prefix}/"
        f"{relative_path.lstrip('/')}"
    )
