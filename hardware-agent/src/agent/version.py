"""The installed hardware-agent version. pyproject.toml is the only copy."""

from __future__ import annotations

from importlib.metadata import version as package_version


def installed_version() -> str:
    # Raises PackageNotFoundError when the agent is not installed. The package and
    # `uv sync` always install it, so a missing version is a broken install.
    return package_version("hardware-agent")


# Capture the release identity once per process. The package metadata can be
# replaced while an idle TUI remains open, so scans compare this snapshot with
# the currently installed metadata before admission.
PROCESS_START_VERSION = installed_version()
