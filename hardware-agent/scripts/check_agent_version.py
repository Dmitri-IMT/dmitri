#!/usr/bin/env python3
"""Fail a pull request that changes hardware-agent/ without a higher version."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "hardware-agent" / "pyproject.toml"


def parse_version(text: str) -> tuple[int, int, int]:
    parts = text.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"version must be MAJOR.MINOR.PATCH, got {text!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def version_is_greater(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def debian_package_version(upstream: str) -> str:
    return f"{'.'.join(str(part) for part in parse_version(upstream))}-1"


def _version_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith('version = "'):
            return line.split('"', 2)[1]
    raise SystemExit("hardware-agent/pyproject.toml has no version")


def affected_packages(changed: set[str]) -> tuple[bool, bool]:
    """Return agent/updater identity effects for paths changed in the checkout."""
    agent_sources = {
        "hardware-agent/packaging/build-deb.sh",
        "hardware-agent/pyproject.toml",
        "hardware-agent/uv.lock",
        "hardware-agent/README.md",
        "hardware-agent/dmitri-agent.service",
        "hardware-agent/packaging/updater-version",
        "hardware-agent/src/agent/transport/signing.py",
    }
    agent_changed = bool(changed & agent_sources) or any(
        path.startswith("hardware-agent/src/") for path in changed
    )
    updater_sources = {
        "hardware-agent/packaging/build-deb.sh",
        "hardware-agent/packaging/updater-version",
        "hardware-agent/packaging/updater.py",
        "hardware-agent/packaging/apt-upgrade-agent",
        "hardware-agent/packaging/scan-lock-path",
        "hardware-agent/packaging/dmitri-agent-update.service",
        "hardware-agent/packaging/dmitri-agent-update.timer",
        "hardware-agent/packaging/dmitri-agent-update-check.service",
        "hardware-agent/src/agent/transport/signing.py",
    }
    return agent_changed, bool(changed & updater_sources)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD", "--", "hardware-agent"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    changed = set(diff.stdout.splitlines())
    if not changed:
        print("hardware-agent/ unchanged")
        return 0

    agent_changed, updater_changed = affected_packages(changed)

    checks: list[tuple[str, str, str]] = []
    if agent_changed:
        current = _version_line(_git("show", f"{base}:hardware-agent/pyproject.toml"))
        candidate = _version_line(PYPROJECT.read_text())
        checks.append(("hardware-agent", current, candidate))
    if updater_changed:
        version_file = ROOT / "hardware-agent" / "packaging" / "updater-version"
        candidate = version_file.read_text().strip()
        parse_version(candidate)
        try:
            current = _git(
                "show", f"{base}:hardware-agent/packaging/updater-version"
            ).strip()
        except subprocess.CalledProcessError:
            current = "0.0.0"
        checks.append(("hardware-agent-updater", current, candidate))

    for package, current, candidate in checks:
        if not version_is_greater(candidate, current):
            print(
                f"{package} changed but {candidate} is not greater than "
                f"{current} on {base}",
                file=sys.stderr,
            )
            return 1
        print(
            f"{package} version {current} -> {candidate} "
            f"(Debian {debian_package_version(candidate)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
