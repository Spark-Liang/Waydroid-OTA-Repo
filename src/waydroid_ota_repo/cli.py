from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .config import build_config, load_publisher_config
from .service import convert

app = typer.Typer(help="Convert and mirror Waydroid OTA manifests.")
console = Console()
DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_DIST_DIR = Path("dist")
ManifestArgument = Annotated[Path, typer.Argument(..., exists=True, dir_okay=False)]
CacheOption = Annotated[Path, typer.Option("--cache-dir")]
DistOption = Annotated[Path, typer.Option("--dist-dir")]
PublisherModeOption = Annotated[str, typer.Option("--publisher-mode")]
PublisherValueOption = Annotated[str, typer.Option("--publisher-value")]
PublisherConfigOption = Annotated[Path | None, typer.Option("--publisher-config")]


@app.command()
def run(
    manifest: ManifestArgument,
    cache_dir: CacheOption = DEFAULT_CACHE_DIR,
    dist_dir: DistOption = DEFAULT_DIST_DIR,
    publisher_mode: PublisherModeOption = "local",
    publisher_value: PublisherValueOption = "dist",
    publisher_config: PublisherConfigOption = None,
) -> None:
    config = build_config(
        manifest_path=manifest,
        cache_dir=cache_dir,
        dist_dir=dist_dir,
        publisher_mode=publisher_mode,
        publisher_value=publisher_value,
    )
    if publisher_config is not None:
        config = config.model_copy(
            update={"publisher": load_publisher_config(publisher_config)}
        )
    result = convert(config)
    console.print(f"manifest: {result.manifest_path}")
    console.print(f"artifacts: {len(result.artifact_paths)}")
