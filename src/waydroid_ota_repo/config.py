from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.type_adapter import TypeAdapter

from .errors import ConfigError
from .models import (
    ConvertConfig,
    GitHubPublisher,
    LocalPublisher,
    NexusRawPublisher,
    Publisher,
    RawProxyRootPublisher,
    RemoteOtaSourceSet,
    UpstreamPublishConfig,
)

GITHUB_PART_COUNT = 2
GITHUB_PUBLISHER_FORMAT_ERROR = "github publisher must be in OWNER/REPO format"
type PublisherMode = Literal["local", "github", "nexus_raw", "raw_proxy_root"]


class PublisherConfigFile(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    publisher: Publisher


class UpstreamPublishConfigFile(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    upstream: RemoteOtaSourceSet
    published_channel: str = "stable"


def load_publisher_config(path: Path) -> Publisher:
    adapter = TypeAdapter(PublisherConfigFile)
    return adapter.validate_json(path.read_text(encoding="utf-8")).publisher


def load_upstream_publish_sources(path: Path) -> RemoteOtaSourceSet:
    adapter = TypeAdapter(UpstreamPublishConfigFile)
    return adapter.validate_json(path.read_text(encoding="utf-8")).upstream


def build_upstream_publish_config(
    *,
    source_config_path: Path,
    cache_dir: Path,
    dist_dir: Path,
    publisher: Publisher,
) -> UpstreamPublishConfig:
    upstream_config = TypeAdapter(UpstreamPublishConfigFile).validate_json(
        source_config_path.read_text(encoding="utf-8")
    )
    return UpstreamPublishConfig(
        upstream=upstream_config.upstream,
        cache_dir=cache_dir,
        dist_dir=dist_dir,
        publisher=publisher,
        published_channel=upstream_config.published_channel,
    )


def build_config(
    manifest_path: Path,
    cache_dir: Path,
    dist_dir: Path,
    publisher_mode: str,
    publisher_value: str,
) -> ConvertConfig:
    publisher = parse_publisher(
        publisher_mode=parse_publisher_mode(publisher_mode),
        value=publisher_value,
    )
    return ConvertConfig(
        upstream_manifest=manifest_path,
        cache_dir=cache_dir,
        dist_dir=dist_dir,
        publisher=publisher,
    )


def parse_publisher(*, publisher_mode: PublisherMode, value: str) -> Publisher:
    match publisher_mode:
        case "local":
            return LocalPublisher(base_path=Path(value))
        case "github":
            parts = value.split("/")
            if len(parts) != GITHUB_PART_COUNT:
                raise ConfigError(GITHUB_PUBLISHER_FORMAT_ERROR)
            return GitHubPublisher(owner=parts[0], repo=parts[1])
        case "nexus_raw":
            return NexusRawPublisher(
                base_url=value,
                repository="waydroid-ota",
            )
        case "raw_proxy_root":
            return RawProxyRootPublisher(base_url=value)


def parse_publisher_mode(value: str) -> PublisherMode:
    adapter: TypeAdapter[PublisherMode] = TypeAdapter(PublisherMode)
    try:
        parsed = adapter.validate_python(value)
    except ValidationError as exc:
        message = f"unsupported publisher mode: {value}"
        raise ConfigError(message) from exc
    return parsed
