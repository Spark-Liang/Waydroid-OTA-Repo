from pathlib import Path
from typing import Protocol

from httpx2 import HTTPError

from .errors import DownloadError, PathWriteError
from .hashing import verify_artifact
from .http import create_client
from .models import Artifact


class Downloader(Protocol):
    def fetch(self, artifact: Artifact) -> bytes:
        ...


class HttpDownloader:
    def fetch(self, artifact: Artifact) -> bytes:
        with create_client() as client:
            try:
                response = client.get(str(artifact.url))
                _ = response.raise_for_status()
            except HTTPError as exc:
                raise DownloadError(url=str(artifact.url), reason=str(exc)) from exc
            return response.content


def ensure_artifact_cached(
    artifact: Artifact,
    cache_dir: Path,
    downloader: Downloader,
) -> Path:
    _ = cache_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = cache_dir / artifact.name
    if not artifact_path.exists():
        content = downloader.fetch(artifact)
        try:
            _ = artifact_path.write_bytes(content)
        except OSError as exc:
            raise PathWriteError(path=artifact_path, reason=str(exc)) from exc
    _ = verify_artifact(artifact_path, artifact)
    return artifact_path
