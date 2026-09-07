from dataclasses import dataclass


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str | None = None
    architecture: str = "x64"
    filename: str = ""
    detection_version: str | None = None
