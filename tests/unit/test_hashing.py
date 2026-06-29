from pathlib import Path

import pytest

from waydroid_ota_repo.errors import ManifestValidationError
from waydroid_ota_repo.hashing import verify_artifact
from waydroid_ota_repo.models import Artifact


def test_verify_artifact_when_hash_and_size_match() -> None:
    fixture = Path("tests/fixtures/cache/system.img")
    artifact = Artifact(
        name="system.img",
        url="https://example.invalid/system.img",
        sha256="f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb",
        size=15,
    )

    digest = verify_artifact(fixture, artifact)

    assert digest.size == 15


def test_verify_artifact_when_hash_mismatches() -> None:
    fixture = Path("tests/fixtures/cache/system.img")
    artifact = Artifact(
        name="system.img",
        url="https://example.invalid/system.img",
        sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        size=15,
    )

    with pytest.raises(ManifestValidationError):
        _ = verify_artifact(fixture, artifact)
