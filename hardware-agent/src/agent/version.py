"""The installed hardware-agent version. pyproject.toml is the only copy."""

from __future__ import annotations

from importlib.metadata import version as package_version


def installed_version() -> str:
    # Raises PackageNotFoundError when the agent is not installed. The package and
    # `uv sync` always install it, so a missing version is a broken install.
    return package_version("hardware-agent")


PROCESS_START_VERSION = installed_version()
