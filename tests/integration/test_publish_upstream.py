import json
from pathlib import Path
from types import TracebackType
from typing import Self

import pytest
from typer.testing import CliRunner

from waydroid_ota_repo.cli import app


def _build_upstream_manifest(*, artifact_name: str, sha256: str, url: str) -> str:
    payload = {
        "response": [
            {
                "filename": artifact_name,
                "id": sha256,
                "romtype": "stable",
                "size": 15,
                "url": url,
                "version": "1.2.3",
                "compression": "none",
            }
        ]
    }
    return json.dumps(payload)


def test_publish_upstream_command_when_mocked_upstream_and_cached_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    cache_dir = tmp_path / "cache"
    dist_dir = tmp_path / "dist"
    upstream_config_path = tmp_path / "upstream.json"
    system_url = "https://example.invalid/system.json"
    vendor_url = "https://example.invalid/vendor.json"
    _ = cache_dir.mkdir()
    system_sha = "f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb"
    vendor_sha = "c83013631a0a5cde4eff2fd787cf86476c567ace81a18aed411d123ec0ff39e3"
    system_cache_dir = cache_dir / system_sha
    vendor_cache_dir = cache_dir / vendor_sha
    _ = system_cache_dir.mkdir(parents=True)
    _ = vendor_cache_dir.mkdir(parents=True)
    _ = (system_cache_dir / "system.img").write_bytes(b"system-image-1\n")
    _ = (vendor_cache_dir / "vendor.img").write_bytes(b"vendor-image-1\n")
    _ = upstream_config_path.write_text(
        json.dumps(
            {
                "upstream": {
                    "system": {"manifest_url": system_url},
                    "vendor": {"manifest_url": vendor_url},
                }
            }
        ),
        encoding="utf-8",
    )

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.text: str = text

        def raise_for_status(self) -> None:
            return

    class _FakeClient:
        def __enter__(self) -> Self:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            payload_by_url = {
                system_url: _build_upstream_manifest(
                    artifact_name="system.img",
                    sha256=system_sha,
                    url="https://cdn.example.invalid/system.img",
                ),
                vendor_url: _build_upstream_manifest(
                    artifact_name="vendor.img",
                    sha256=vendor_sha,
                    url="https://cdn.example.invalid/vendor.img",
                ),
            }
            return _FakeResponse(payload_by_url[url])

    def _fake_client_factory() -> _FakeClient:
        return _FakeClient()

    monkeypatch.setattr(
        "waydroid_ota_repo.upstream.create_client",
        _fake_client_factory,
    )

    result = runner.invoke(
        app,
        [
            "--upstream-config",
            str(upstream_config_path),
            "--cache-dir",
            str(cache_dir),
            "--dist-dir",
            str(dist_dir),
            "--publisher-config",
            "tests/fixtures/raw_proxy_root_publisher.json",
        ],
    )

    assert result.exit_code == 0
    manifest_text = (dist_dir / "manifest.json").read_text(encoding="utf-8")
    assert '"version": "1.2.3"' in manifest_text
    assert "http://127.0.0.1:8000/system/artifacts/system.img" in manifest_text
    assert (dist_dir / "vendor" / "artifacts" / "vendor.img").read_bytes() == (
        b"vendor-image-1\n"
    )
