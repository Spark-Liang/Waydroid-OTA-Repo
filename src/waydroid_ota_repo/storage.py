from pathlib import Path
from typing import Protocol

from httpx2 import HTTPError

from .errors import DownloadError, ManifestValidationError, PathWriteError
from .hashing import verify_artifact
from .http import create_client
from .models import Artifact


class Downloader(Protocol):
    def fetch_to_path(self, artifact: Artifact, destination: Path) -> None:
        ...


class HttpDownloader:
    def fetch_to_path(self, artifact: Artifact, destination: Path) -> None:
        with create_client() as client:
            try:
                with client.stream("GET", str(artifact.url)) as response:
                    _ = response.raise_for_status()
                    with destination.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            _ = handle.write(chunk)
            except HTTPError as exc:
                raise DownloadError(url=str(artifact.url), reason=str(exc)) from exc
            except OSError as exc:
                raise PathWriteError(path=destination, reason=str(exc)) from exc


def _render_cache_path(*, cache_dir: Path, artifact: Artifact) -> Path:
    return cache_dir / artifact.sha256 / artifact.name


def _remove_file_if_exists(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.unlink()
    except OSError as exc:
        raise PathWriteError(path=path, reason=str(exc)) from exc


def _replace_with_verified_download(
    *, artifact: Artifact, downloader: Downloader, artifact_path: Path
) -> None:
    _ = artifact_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = artifact_path.with_suffix(f"{artifact_path.suffix}.part")
    _remove_file_if_exists(temporary_path)
    downloader.fetch_to_path(artifact, temporary_path)
    _ = verify_artifact(temporary_path, artifact)
    try:
        _ = temporary_path.replace(artifact_path)
    except OSError as exc:
        raise PathWriteError(path=artifact_path, reason=str(exc)) from exc


def ensure_artifact_cached(
    artifact: Artifact,
    cache_dir: Path,
    downloader: Downloader,
) -> Path:
    _ = cache_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = _render_cache_path(cache_dir=cache_dir, artifact=artifact)
    legacy_artifact_path = cache_dir / artifact.name
    if artifact_path.exists():
        try:
            _ = verify_artifact(artifact_path, artifact)
        except ManifestValidationError:
            _remove_file_if_exists(artifact_path)
        else:
            return artifact_path
    if legacy_artifact_path.exists():
        try:
            _ = verify_artifact(legacy_artifact_path, artifact)
            _ = artifact_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                _ = legacy_artifact_path.replace(artifact_path)
            except OSError as exc:
                raise PathWriteError(path=artifact_path, reason=str(exc)) from exc
        except ManifestValidationError:
            _remove_file_if_exists(legacy_artifact_path)
        else:
            return artifact_path
    _replace_with_verified_download(
        artifact=artifact,
        downloader=downloader,
        artifact_path=artifact_path,
    )
    _ = verify_artifact(artifact_path, artifact)
    return artifact_path
