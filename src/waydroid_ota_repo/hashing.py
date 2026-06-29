import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import ManifestValidationError
from .models import Artifact


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    sha256: str
    size: int


def compute_digest(path: Path) -> ArtifactDigest:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return ArtifactDigest(sha256=digest.hexdigest(), size=size)


def verify_artifact(path: Path, artifact: Artifact) -> ArtifactDigest:
    digest = compute_digest(path)
    if digest.size != artifact.size:
        raise ManifestValidationError(
            artifact_name=artifact.name,
            reason=f"size mismatch: expected {artifact.size}, got {digest.size}",
        )
    if digest.sha256 != artifact.sha256:
        raise ManifestValidationError(
            artifact_name=artifact.name,
            reason=(
                f"sha256 mismatch: expected {artifact.sha256}, got {digest.sha256}"
            ),
        )
    return digest
