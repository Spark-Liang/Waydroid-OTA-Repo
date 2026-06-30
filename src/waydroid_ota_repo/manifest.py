import json
from pathlib import Path

from .models import ReleaseIndex, UpstreamManifest


def load_manifest(path: Path) -> UpstreamManifest:
    return UpstreamManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_manifest_text(payload: str) -> UpstreamManifest:
    return UpstreamManifest.model_validate_json(payload)


def dump_manifest(manifest: UpstreamManifest, path: Path) -> None:
    _ = path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        manifest.model_dump(mode="json"), indent=2, sort_keys=True
    )
    _ = path.write_text(f"{rendered}\n", encoding="utf-8")


def dump_release_index(index: ReleaseIndex, path: Path) -> None:
    _ = path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(index.model_dump(mode="json"), indent=2, sort_keys=True)
    _ = path.write_text(f"{rendered}\n", encoding="utf-8")


def load_release_index(path: Path) -> ReleaseIndex | None:
    if not path.exists():
        return None
    return ReleaseIndex.model_validate_json(path.read_text(encoding="utf-8"))


def dump_json_payload(*, payload: dict[str, object], path: Path) -> None:
    _ = path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    _ = path.write_text(f"{rendered}\n", encoding="utf-8")
