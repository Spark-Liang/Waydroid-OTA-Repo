from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    computed_field,
    model_validator,
)

type CompatibilityScalar = str | int | None
type CompatibilityArtifactPayload = dict[str, CompatibilityScalar]
type CompatibilityResponse = list[CompatibilityArtifactPayload]
type CompatibilityManifestValue = CompatibilityScalar | CompatibilityResponse
type CompatibilityManifestPayload = dict[str, CompatibilityManifestValue]
STRING_OBJECT_MAPPING_ADAPTER = TypeAdapter(dict[str, object])
STRING_OBJECT_MAPPING_LIST_ADAPTER = TypeAdapter(list[dict[str, object]])


def _string_key_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return STRING_OBJECT_MAPPING_ADAPTER.validate_python(value)


def _parse_compatibility_scalar(value: object) -> CompatibilityScalar | None:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if value is None:
        return None
    return None


def _normalize_artifact_mapping(
    value: Mapping[str, object],
) -> CompatibilityArtifactPayload:
    payload: CompatibilityArtifactPayload = {}
    for key, item in value.items():
        normalized_item = _parse_compatibility_scalar(item)
        if normalized_item is not None:
            payload[key] = normalized_item
        if item is None:
            payload[key] = None
    return payload


def _normalize_manifest_mapping(
    value: Mapping[str, object],
) -> CompatibilityManifestPayload:
    payload: CompatibilityManifestPayload = {}
    for key, item in value.items():
        normalized_item = _parse_compatibility_scalar(item)
        if normalized_item is not None:
            payload[key] = normalized_item
            continue
        if item is None:
            payload[key] = None
            continue
        if isinstance(item, list):
            normalized_items: CompatibilityResponse = []
            normalized_entry_list = STRING_OBJECT_MAPPING_LIST_ADAPTER.validate_python(
                item
            )
            for normalized_entry in normalized_entry_list:
                normalized_items.append(_normalize_artifact_mapping(normalized_entry))
            payload[key] = normalized_items
    return payload


def _normalize_existing_manifest_sequence(
    value: object,
) -> CompatibilityResponse | None:
    if not isinstance(value, list):
        return None
    normalized_items: CompatibilityResponse = []
    normalized_item_list = STRING_OBJECT_MAPPING_LIST_ADAPTER.validate_python(value)
    for normalized_item in normalized_item_list:
        normalized_items.append(_normalize_artifact_mapping(normalized_item))
    return normalized_items


def _is_absolute_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.netloc != ""


class Artifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    name: str
    url: str
    sha256: str = Field(min_length=64, max_length=64)
    size: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_waydroid_fields(cls, value: object) -> object:
        mapping = _string_key_mapping(value)
        if mapping is None:
            return value

        payload = _normalize_artifact_mapping(mapping)
        if "name" not in payload and "filename" in payload:
            payload["name"] = payload["filename"]
        artifact_id = payload.get("id")
        if "sha256" not in payload and isinstance(artifact_id, str):
            payload["sha256"] = artifact_id
        return payload


class UpstreamManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", frozen=True)

    version: str
    channel: str | None = None
    artifacts: tuple[Artifact, ...]
    response: tuple[Artifact, ...] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_compatibility_payload(cls, value: object) -> object:
        mapping = _string_key_mapping(value)
        if mapping is None:
            return value
        existing_artifacts = mapping.get("artifacts")
        if existing_artifacts is not None and not isinstance(existing_artifacts, list):
            return value

        payload = _normalize_manifest_mapping(mapping)
        normalized_existing_artifacts = _normalize_existing_manifest_sequence(
            mapping.get("artifacts")
        )
        if normalized_existing_artifacts is not None:
            payload["artifacts"] = normalized_existing_artifacts
        normalized_existing_response = _normalize_existing_manifest_sequence(
            mapping.get("response")
        )
        if normalized_existing_response is not None:
            payload["response"] = normalized_existing_response
        response_items = payload.get("response")
        if "artifacts" not in payload and isinstance(response_items, list):
            payload["artifacts"] = response_items

        first_response = (
            response_items[0]
            if isinstance(response_items, list) and len(response_items) > 0
            else None
        )
        if "version" not in payload and first_response is not None:
            response_version = first_response.get("version")
            if isinstance(response_version, str):
                payload["version"] = response_version
        if payload.get("channel") is None and first_response is not None:
            response_channel = first_response.get("romtype")
            if isinstance(response_channel, str):
                payload["channel"] = response_channel
        return payload


class LocalPublisher(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: Literal["local"] = "local"
    base_path: Path


class GitHubPublisher(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: Literal["github"] = "github"
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    branch: str = Field(default="main", min_length=1)
    pages_prefix: str = Field(default="ota")
    release_tag: str = Field(default="latest", min_length=1)
    use_releases_for_artifacts: bool = True

    @computed_field
    @property
    def pages_manifest_url(self) -> str:
        prefix = self.pages_prefix.strip("/")
        return (
            f"https://{self.owner}.github.io/{self.repo}/{prefix}/manifest.json"
        )


class NexusRawPublisher(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: Literal["nexus_raw"] = "nexus_raw"
    base_url: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    directory_prefix: str = Field(default="waydroid-ota")


class RawProxyRootPublisher(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: Literal["raw_proxy_root"] = "raw_proxy_root"
    base_url: str = Field(min_length=1)


class RemoteOtaManifestSource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    manifest_url: str

    @model_validator(mode="after")
    def validate_absolute_http_url(self) -> "RemoteOtaManifestSource":
        if not _is_absolute_http_url(self.manifest_url):
            msg = "manifest_url must be an absolute http(s) URL"
            raise ValueError(msg)
        return self


class RemoteOtaSourceSet(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    system: RemoteOtaManifestSource
    vendor: RemoteOtaManifestSource


class UpstreamPublishConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cache_dir: Path
    dist_dir: Path
    publisher: "Publisher"
    upstream: RemoteOtaSourceSet
    published_channel: str = Field(default="stable", min_length=1)


class RemoteArtifact(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    url: str

    @model_validator(mode="after")
    def validate_absolute_http_url(self) -> "RemoteArtifact":
        if not _is_absolute_http_url(self.url):
            msg = f"artifact {self.name!r} url must be an absolute http(s) URL"
            raise ValueError(msg)
        return self


class ReleaseMetadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    version: str
    manifest_url: str
    published_at: str | None = None


class ReleaseIndex(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    latest_version: str
    latest_manifest_url: str
    releases: tuple[ReleaseMetadata, ...]


class ReleasePlan(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    version: str
    versioned_manifest_path: Path
    latest_manifest_path: Path
    release_index_path: Path
    latest_index_path: Path
    versioned_artifacts_dir: Path
    latest_artifacts_dir: Path
    versioned_manifest_url: str
    latest_manifest_url: str
    release_index_url: str


class RawProxyChannelPlan(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    role: Literal["system", "vendor"]
    channel: str
    version: str
    latest_channel_manifest_path: Path
    latest_alias_manifest_path: Path
    versioned_manifest_path: Path
    artifacts_dir: Path
    artifact_base_url: str


type Publisher = (
    LocalPublisher | GitHubPublisher | NexusRawPublisher | RawProxyRootPublisher
)


class ConvertConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    upstream_manifest: Path
    cache_dir: Path
    dist_dir: Path
    publisher: Publisher


_ = UpstreamPublishConfig.model_rebuild()
