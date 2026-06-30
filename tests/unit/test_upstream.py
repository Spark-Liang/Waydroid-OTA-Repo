import json
from pathlib import Path
from typing import Self

import pytest

from waydroid_ota_repo.errors import UpstreamFetchError
from waydroid_ota_repo.models import RemoteOtaManifestSource, RemoteOtaSourceSet
from waydroid_ota_repo.upstream import (
    fetch_upstream_manifest_set,
    publish_artifact_copy,
)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text: str = text

    def raise_for_status(self) -> None:
        return


class _FakeClient:
    def __init__(self, payload_by_url: dict[str, str]) -> None:
        self._payload_by_url: dict[str, str] = payload_by_url

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(self._payload_by_url[url])


def test_fetch_upstream_manifest_set_when_partition_manifests_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_url = "https://example.invalid/system.json"
    vendor_url = "https://example.invalid/vendor.json"
    system_manifest = (
        '{"response":[{"filename":"system.img","id":"'
        "f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb"
        '","romtype":"stable","size":15,"url":"https://ota.example.invalid/waydroid/system.img",'
        '"version":"1.2.3","compression":"none"}]}'
    )
    vendor_manifest = (
        '{"response":[{"filename":"vendor.img","id":"'
        "c83013631a0a5cde4eff2fd787cf86476c567ace81a18aed411d123ec0ff39e3"
        '","romtype":"stable","size":15,"url":"https://ota.example.invalid/waydroid/vendor.img",'
        '"version":"1.2.3","compression":"none"}]}'
    )
    payload_by_url = {system_url: system_manifest, vendor_url: vendor_manifest}
    monkeypatch.setattr(
        "waydroid_ota_repo.upstream.create_client",
        lambda: _FakeClient(payload_by_url),
    )

    manifest = fetch_upstream_manifest_set(
        RemoteOtaSourceSet(
            system=RemoteOtaManifestSource(manifest_url=str(system_url)),
            vendor=RemoteOtaManifestSource(manifest_url=str(vendor_url)),
        )
    )

    assert manifest.version == "1.2.3"
    assert manifest.channel == "stable"
    assert tuple(artifact.name for artifact in manifest.artifacts) == (
        "system.img",
        "vendor.img",
    )


def test_fetch_upstream_manifest_set_when_partition_channels_differ_still_merges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_url = "https://example.invalid/system.json"
    vendor_url = "https://example.invalid/vendor.json"
    system_manifest = (
        '{"response":[{"filename":"system.img","id":"'
        "f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb"
        '","romtype":"VANILLA","size":15,"url":"https://ota.example.invalid/waydroid/system.img",'
        '"version":"1.2.3","compression":"none"}]}'
    )
    vendor_manifest = (
        '{"response":[{"filename":"vendor.img","id":"'
        "c83013631a0a5cde4eff2fd787cf86476c567ace81a18aed411d123ec0ff39e3"
        '","romtype":"MAINLINE","size":15,"url":"https://ota.example.invalid/waydroid/vendor.img",'
        '"version":"1.2.3","compression":"none"}]}'
    )
    payload_by_url = {system_url: system_manifest, vendor_url: vendor_manifest}
    monkeypatch.setattr(
        "waydroid_ota_repo.upstream.create_client",
        lambda: _FakeClient(payload_by_url),
    )

    manifest = fetch_upstream_manifest_set(
        RemoteOtaSourceSet(
            system=RemoteOtaManifestSource(manifest_url=str(system_url)),
            vendor=RemoteOtaManifestSource(manifest_url=str(vendor_url)),
        )
    )

    assert manifest.version == "1.2.3"
    assert manifest.channel == "VANILLA"


def test_fetch_upstream_manifest_set_when_versions_differ_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_url = "https://example.invalid/system.json"
    vendor_url = "https://example.invalid/vendor.json"
    system_manifest = (
        '{"response":[{"filename":"system.img","id":"'
        "f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb"
        '","romtype":"stable","size":15,"url":"https://ota.example.invalid/waydroid/system.img",'
        '"version":"1.2.3","compression":"none"}]}'
    )
    vendor_manifest = (
        '{"response":[{"filename":"vendor.img","id":"'
        "c83013631a0a5cde4eff2fd787cf86476c567ace81a18aed411d123ec0ff39e3"
        '","romtype":"stable","size":15,"url":"https://ota.example.invalid/waydroid/vendor.img",'
        '"version":"1.2.4","compression":"none"}]}'
    )
    payload_by_url = {system_url: system_manifest, vendor_url: vendor_manifest}
    monkeypatch.setattr(
        "waydroid_ota_repo.upstream.create_client",
        lambda: _FakeClient(payload_by_url),
    )

    with pytest.raises(UpstreamFetchError, match="versions differ"):
        _ = fetch_upstream_manifest_set(
            RemoteOtaSourceSet(
                system=RemoteOtaManifestSource(manifest_url=str(system_url)),
                vendor=RemoteOtaManifestSource(manifest_url=str(vendor_url)),
            )
        )


def test_publish_artifact_copy_when_large_payload_copies_bytes(tmp_path: Path) -> None:
    source_path = tmp_path / "source.img"
    target_path = tmp_path / "nested" / "target.img"
    payload = b"abc123" * (1024 * 256)
    _ = source_path.write_bytes(payload)

    publish_artifact_copy(artifact_path=source_path, target_path=target_path)

    assert target_path.read_bytes() == payload


SYSTEM_SHA = (
    "f8dc5cfdcda58e7de061e6870641a49c4b911cdba44c1b482fd9f9211b1987bb"
)
VENDOR_SHA = (
    "c83013631a0a5cde4eff2fd787cf86476c567ace81a18aed411d123ec0ff39e3"
)


def test_fetch_upstream_manifest_set_when_partition_has_many_history_entries_use_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_url = "https://example.invalid/system.json"
    vendor_url = "https://example.invalid/vendor.json"
    system_manifest = json.dumps(
        {
            "response": [
                {
                    "filename": "system-old.img",
                    "id": SYSTEM_SHA,
                    "romtype": "VANILLA",
                    "size": 15,
                    "url": "https://ota.example.invalid/waydroid/system-old.img",
                    "version": "1.2.3",
                    "compression": "none",
                    "datetime": 1,
                },
                {
                    "filename": "system-new.img",
                    "id": SYSTEM_SHA,
                    "romtype": "VANILLA",
                    "size": 15,
                    "url": "https://ota.example.invalid/waydroid/system-new.img",
                    "version": "1.2.3",
                    "compression": "none",
                    "datetime": 2,
                },
            ]
        }
    )
    vendor_manifest = json.dumps(
        {
            "response": [
                {
                    "filename": "vendor-old.img",
                    "id": VENDOR_SHA,
                    "romtype": "MAINLINE",
                    "size": 15,
                    "url": "https://ota.example.invalid/waydroid/vendor-old.img",
                    "version": "1.2.3",
                    "compression": "none",
                    "datetime": 1,
                },
                {
                    "filename": "vendor-new.img",
                    "id": VENDOR_SHA,
                    "romtype": "MAINLINE",
                    "size": 15,
                    "url": "https://ota.example.invalid/waydroid/vendor-new.img",
                    "version": "1.2.3",
                    "compression": "none",
                    "datetime": 2,
                },
            ]
        }
    )
    payload_by_url = {system_url: system_manifest, vendor_url: vendor_manifest}
    monkeypatch.setattr(
        "waydroid_ota_repo.upstream.create_client",
        lambda: _FakeClient(payload_by_url),
    )

    manifest = fetch_upstream_manifest_set(
        RemoteOtaSourceSet(
            system=RemoteOtaManifestSource(manifest_url=str(system_url)),
            vendor=RemoteOtaManifestSource(manifest_url=str(vendor_url)),
        )
    )

    assert tuple(artifact.name for artifact in manifest.artifacts) == (
        "system-new.img",
        "vendor-new.img",
    )
