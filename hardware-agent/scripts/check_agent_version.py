#!/usr/bin/env python3
"""Fail a pull request that changes hardware-agent/ without a higher version."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agent.version import version_is_greater

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "hardware-agent" / "pyproject.toml"


def _version_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith('version = "'):
            return line.split('"', 2)[1]
    raise SystemExit("hardware-agent/pyproject.toml has no version")


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
    if not diff.stdout.strip():
        print("hardware-agent/ unchanged")
        return 0
    current = _version_line(_git("show", f"{base}:hardware-agent/pyproject.toml"))
    candidate = _version_line(PYPROJECT.read_text())
    if not version_is_greater(candidate, current):
        message = (
            f"hardware-agent changed but {candidate} "
            f"is not greater than {current} on {base}"
        )
        print(message, file=sys.stderr)
        return 1
    print(f"hardware-agent version {current} -> {candidate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
