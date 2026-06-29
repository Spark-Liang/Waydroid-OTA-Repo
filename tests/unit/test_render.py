from pathlib import Path

from waydroid_ota_repo.manifest import load_manifest
from waydroid_ota_repo.models import GitHubPublisher, LocalPublisher, NexusRawPublisher
from waydroid_ota_repo.render import build_release_plan, rewrite_manifest


def test_rewrite_manifest_when_local_publisher_preserves_shape() -> None:
    manifest = load_manifest(Path("tests/fixtures/upstream_manifest.json"))

    rewritten = rewrite_manifest(manifest, LocalPublisher(base_path=Path("dist")))

    assert rewritten.channel == "stable"
    assert rewritten.artifacts[0].url == "dist/latest/artifacts/system.img"


def test_rewrite_manifest_when_github_publisher_uses_release_urls() -> None:
    manifest = load_manifest(Path("tests/fixtures/upstream_manifest.json"))
    publisher = GitHubPublisher(owner="Spark-Liang", repo="Waydroid-OTA-Repo")

    rewritten = rewrite_manifest(manifest, publisher)

    assert rewritten.artifacts[1].url == (
        "https://github.com/Spark-Liang/Waydroid-OTA-Repo/releases/download/latest/vendor.img"
    )


def test_rewrite_manifest_when_waydroid_fixture_preserves_response_fields() -> None:
    manifest = load_manifest(Path("tests/fixtures/upstream_manifest_waydroid.json"))

    rewritten = rewrite_manifest(manifest, LocalPublisher(base_path=Path("dist")))

    assert rewritten.version == "1.2.3"
    assert rewritten.channel == "stable"
    assert rewritten.response is not None
    assert rewritten.response[0].name == "system.img"
    assert rewritten.response[0].url == "dist/latest/artifacts/system.img"
    assert rewritten.response[0].model_dump(mode="python")["romtype"] == "stable"


def test_rewrite_manifest_when_nexus_raw_publisher_renders_latest_urls() -> None:
    manifest = load_manifest(Path("tests/fixtures/upstream_manifest.json"))
    publisher = NexusRawPublisher(
        base_url="https://nexus.example.invalid/",
        repository="waydroid-ota",
        directory_prefix="android/waydroid",
    )

    rewritten = rewrite_manifest(manifest, publisher)

    assert rewritten.artifacts[0].url == (
        "https://nexus.example.invalid/repository/waydroid-ota/"
        "android/waydroid/latest/artifacts/system.img"
    )


def test_build_release_plan_when_local_publisher_exposes_metadata_paths() -> None:
    publisher = LocalPublisher(base_path=Path("dist"))

    plan = build_release_plan(
        dist_dir=Path("dist"),
        version="1.2.3",
        publisher=publisher,
    )

    assert plan.version == "1.2.3"
    assert plan.latest_manifest_path == Path("dist/manifest.json")
    assert plan.release_index_path == Path("dist/releases/index.json")
    assert plan.latest_index_path == Path("dist/latest.json")
    assert plan.versioned_artifacts_dir == Path("dist/releases/1.2.3/artifacts")
    assert plan.latest_artifacts_dir == Path("dist/latest/artifacts")


def test_build_release_plan_when_nexus_publisher_exposes_metadata_urls() -> None:
    publisher = NexusRawPublisher(
        base_url="https://nexus.example.invalid/",
        repository="waydroid-ota",
        directory_prefix="android/waydroid",
    )

    plan = build_release_plan(
        dist_dir=Path("dist"),
        version="1.2.3",
        publisher=publisher,
    )

    assert plan.versioned_manifest_url == (
        "https://nexus.example.invalid/repository/waydroid-ota/"
        "android/waydroid/releases/1.2.3/manifest.json"
    )
    assert plan.latest_manifest_url == (
        "https://nexus.example.invalid/repository/waydroid-ota/"
        "android/waydroid/manifest.json"
    )
    assert plan.release_index_url == (
        "https://nexus.example.invalid/repository/waydroid-ota/"
        "android/waydroid/releases/index.json"
    )
