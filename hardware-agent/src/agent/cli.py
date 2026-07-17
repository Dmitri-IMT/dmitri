"""CLI dispatcher for the dmitri command."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main() -> None:
    """Entry point: 'dmitri start' or bare 'dmitri' launches the TUI."""
    args = sys.argv[1:]

    if not args or args[0] == "start":
        _run_tui()
    elif args[0] == "agent":
        _run_agent(args[1:])
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        print("Usage: dmitri [start|agent <mode> <subnet>]", file=sys.stderr)
        raise SystemExit(2)


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
        raise SystemExit(20)

    from agent.tui.app import DmitriApp

    app = DmitriApp()
    app.run()


def _run_agent(args: list[str]) -> None:
    if len(args) != 2:
        print("Usage: dmitri agent <mode> <subnet>", file=sys.stderr)
        raise SystemExit(2)

    if not _check_nmap():
        print("Error: nmap is not installed or not on PATH.", file=sys.stderr)
        print("Install nmap: https://nmap.org/download.html", file=sys.stderr)
        raise SystemExit(20)

    from agent import headless

    mode, subnet = args
    try:
        result = headless.run_headless_scan(
            mode, subnet, reporter=headless.StderrReporter()
        )
    except headless.InvalidScanInput as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    scan_id = str(result.payload.scan_id) if result.payload is not None else None
    result_path = str(result.result_path) if result.result_path is not None else None
    print(
        json.dumps(
            {"outcome": result.outcome, "result_path": result_path, "scan_id": scan_id}
        )
    )
    if result.error is not None:
        print(str(result.error), file=sys.stderr)
    raise SystemExit(headless.EXIT_CODES[result.outcome])


if __name__ == "__main__":
    main()
