from pathlib import Path
from typing import override


class ManifestValidationError(Exception):
    artifact_name: str
    reason: str

    def __init__(self, *, artifact_name: str, reason: str) -> None:  # noqa: D107
        self.artifact_name = artifact_name
        self.reason = reason
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        return f"artifact {self.artifact_name!r} is invalid: {self.reason}"


class ConfigError(Exception):
    reason: str

    def __init__(self, reason: str) -> None:  # noqa: D107
        self.reason = reason
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        return self.reason


class DownloadError(Exception):
    url: str
    reason: str

    def __init__(self, *, url: str, reason: str) -> None:  # noqa: D107
        self.url = url
        self.reason = reason
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        return f"failed to download {self.url}: {self.reason}"


class UpstreamFetchError(Exception):
    url: str
    reason: str

    def __init__(self, *, url: str, reason: str) -> None:  # noqa: D107
        self.url = url
        self.reason = reason
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        return f"failed to fetch upstream manifest {self.url}: {self.reason}"


class PathWriteError(Exception):
    path: Path
    reason: str

    def __init__(self, *, path: Path, reason: str) -> None:  # noqa: D107
        self.path = path
        self.reason = reason
        super().__init__(str(self))

    @override
    def __str__(self) -> str:
        return f"failed to write {self.path}: {self.reason}"
