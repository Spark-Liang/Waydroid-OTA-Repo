from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .config import (
    build_config,
    build_upstream_publish_config,
    load_publisher_config,
    parse_publisher,
    parse_publisher_mode,
)
from .service import convert, publish_upstream

app = typer.Typer(help="Convert and mirror Waydroid OTA manifests.")
console = Console()
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_DIST_DIR = Path("dist")
ManifestArgument = Annotated[Path | None, typer.Argument()]
CacheOption = Annotated[Path, typer.Option("--cache-dir")]
DistOption = Annotated[Path, typer.Option("--dist-dir")]
PublisherModeOption = Annotated[str, typer.Option("--publisher-mode")]
PublisherValueOption = Annotated[str, typer.Option("--publisher-value")]
PublisherConfigOption = Annotated[Path | None, typer.Option("--publisher-config")]
UpstreamConfigOption = Annotated[Path, typer.Option("--upstream-config", exists=True)]


@app.command()
def run(
    manifest: ManifestArgument = None,
    cache_dir: CacheOption = DEFAULT_CACHE_DIR,
    dist_dir: DistOption = DEFAULT_DIST_DIR,
    publisher_mode: PublisherModeOption = "raw_proxy_root",
    publisher_value: PublisherValueOption = "https://example.invalid/ota",
    publisher_config: PublisherConfigOption = None,
    upstream_config: UpstreamConfigOption | None = None,
) -> None:
    publisher = parse_publisher(
        publisher_mode=parse_publisher_mode(publisher_mode),
        value=publisher_value,
    )
    if publisher_config is not None:
        publisher = load_publisher_config(publisher_config)
    if upstream_config is not None:
        config = build_upstream_publish_config(
            source_config_path=upstream_config,
            cache_dir=cache_dir,
            dist_dir=dist_dir,
            publisher=publisher,
        )
        result = publish_upstream(config)
        console.print(f"manifest: {result.manifest_path}")
        console.print(f"artifacts: {len(result.artifact_paths)}")
        return
    if manifest is None:
        raise typer.BadParameter(
            "manifest path is required when --upstream-config is absent"
        )
    config = build_config(
        manifest_path=manifest,
        cache_dir=cache_dir,
        dist_dir=dist_dir,
        publisher_mode=publisher_mode,
        publisher_value=publisher_value,
    )
    if publisher_config is not None:
        config = config.model_copy(update={"publisher": publisher})
    result = convert(config)
    console.print(f"manifest: {result.manifest_path}")
    console.print(f"artifacts: {len(result.artifact_paths)}")
