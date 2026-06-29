from dataclasses import dataclass
from pathlib import Path
from typing import override


@dataclass(frozen=True, slots=True)
class ManifestValidationError(Exception):
    artifact_name: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"artifact {self.artifact_name!r} is invalid: {self.reason}"


@dataclass(frozen=True, slots=True)
class ConfigError(Exception):
    reason: str

    @override
    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class DownloadError(Exception):
    url: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"failed to download {self.url}: {self.reason}"


@dataclass(frozen=True, slots=True)
class PathWriteError(Exception):
    path: Path
    reason: str

    @override
    def __str__(self) -> str:
        return f"failed to write {self.path}: {self.reason}"
