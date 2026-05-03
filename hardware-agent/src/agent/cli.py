"""CLI dispatcher for the dmitri command."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> None:
    """Entry point: 'dmitri start' or bare 'dmitri' launches the TUI."""
    args = sys.argv[1:]

    if not args or args[0] == "start":
        _run_tui()
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        print("Usage: dmitri [start]", file=sys.stderr)
        raise SystemExit(1)


def _check_nmap() -> bool:
    """Return True if nmap is available on PATH or common locations."""
    if shutil.which("nmap"):
        return True
    common_locations = (
        Path("/usr/bin/nmap"),
        Path("/usr/local/bin/nmap"),
        Path(r"C:\Program Files (x86)\Nmap\nmap.exe"),
        Path(r"C:\Program Files\Nmap\nmap.exe"),
    )
    return any(p.exists() for p in common_locations)


def _run_tui() -> None:
    if not _check_nmap():
        print("Error: nmap is not installed or not on PATH.", file=sys.stderr)
        print("Install nmap: https://nmap.org/download.html", file=sys.stderr)
        raise SystemExit(1)

    from agent.tui.app import DmitriApp

    app = DmitriApp()
    app.run()


if __name__ == "__main__":
    main()
