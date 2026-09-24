"""The installed hardware-agent version. pyproject.toml is the only copy."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version


def installed_version() -> str:
    try:
        return package_version("hardware-agent")
    except PackageNotFoundError:
        return "unknown"


def parse_version(text: str) -> tuple[int, int, int]:
    parts = text.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"version must be MAJOR.MINOR.PATCH, got {text!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def version_is_greater(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)
