from pathlib import Path

from typer.testing import CliRunner

from waydroid_ota_repo.cli import app


def _write_cached_artifacts(cache_dir: Path) -> None:
    system_fixture = Path("tests/fixtures/cache/system.img")
    vendor_fixture = Path("tests/fixtures/cache/vendor.img")
    _ = (cache_dir / "system.img").write_bytes(system_fixture.read_bytes())
    _ = (cache_dir / "vendor.img").write_bytes(vendor_fixture.read_bytes())


def _write_manifest(path: Path, *, version: str) -> None:
    template = Path("tests/fixtures/upstream_manifest.json").read_text(
        encoding="utf-8"
    )
    rendered = template.replace('"1.2.3"', f'"{version}"', 1)
    _ = path.write_text(rendered, encoding="utf-8")


def test_convert_flow_when_fixtures_are_cached(tmp_path: Path) -> None:
    runner = CliRunner()
    cache_dir = tmp_path / "cache"
    dist_dir = tmp_path / "dist"
    _ = cache_dir.mkdir()
    _write_cached_artifacts(cache_dir)

    result = runner.invoke(
        app,
        [
            "tests/fixtures/upstream_manifest.json",
            "--cache-dir",
            str(cache_dir),
            "--dist-dir",
            str(dist_dir),
            "--publisher-config",
            "tests/fixtures/github_publisher.json",
        ],
    )

    assert result.exit_code == 0
    assert (dist_dir / "manifest.json").exists()
    assert (dist_dir / "latest.json").exists()
    assert (dist_dir / "releases" / "1.2.3" / "manifest.json").exists()
    assert (dist_dir / "releases" / "index.json").exists()
    manifest_text = (dist_dir / "manifest.json").read_text(encoding="utf-8")
    latest_index_text = (dist_dir / "latest.json").read_text(encoding="utf-8")
    assert "releases/download/latest/system.img" in manifest_text
    assert '"latest_version": "1.2.3"' in latest_index_text
    assert (
        dist_dir / "releases" / "1.2.3" / "artifacts" / "system.img"
    ).read_bytes() == b"system-image-1\n"
    assert (
        dist_dir / "latest" / "artifacts" / "system.img"
    ).read_bytes() == b"system-image-1\n"
    assert (
        dist_dir / "latest" / "artifacts" / "vendor.img"
    ).read_bytes() == b"vendor-image-1\n"


def test_convert_flow_when_two_versions_are_converted_updates_latest_only(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    cache_dir = tmp_path / "cache"
    dist_dir = tmp_path / "dist"
    manifest_v1 = tmp_path / "upstream_manifest_v1.json"
    manifest_v2 = tmp_path / "upstream_manifest_v2.json"
    _ = cache_dir.mkdir()
    _write_cached_artifacts(cache_dir)
    _write_manifest(manifest_v1, version="1.2.3")
    _write_manifest(manifest_v2, version="1.2.4")

    result_v1 = runner.invoke(
        app,
        [
            str(manifest_v1),
            "--cache-dir",
            str(cache_dir),
            "--dist-dir",
            str(dist_dir),
            "--publisher-config",
            "tests/fixtures/github_publisher.json",
        ],
    )
    result_v2 = runner.invoke(
        app,
        [
            str(manifest_v2),
            "--cache-dir",
            str(cache_dir),
            "--dist-dir",
            str(dist_dir),
            "--publisher-config",
            "tests/fixtures/github_publisher.json",
        ],
    )

    assert result_v1.exit_code == 0
    assert result_v2.exit_code == 0
    assert (dist_dir / "releases" / "1.2.3" / "manifest.json").exists()
    assert (dist_dir / "releases" / "1.2.4" / "manifest.json").exists()
    latest_manifest_text = (dist_dir / "manifest.json").read_text(encoding="utf-8")
    release_index_text = (dist_dir / "releases" / "index.json").read_text(
        encoding="utf-8"
    )
    assert '"version": "1.2.4"' in latest_manifest_text
    assert '"latest_version": "1.2.4"' in release_index_text
    assert '"version": "1.2.3"' in release_index_text
    assert '"version": "1.2.4"' in release_index_text
