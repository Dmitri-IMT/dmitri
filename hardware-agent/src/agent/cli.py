"""CLI dispatcher for the dmitri command."""

from __future__ import annotations

import json
import os
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
    elif args == ["health", "--json"]:
        _run_health()
    elif args == ["provision"]:
        from agent.transport.provision import main as provision

        provision()
    else:
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        print(
            "Usage: dmitri [start|health --json|provision|agent "
            "[<mode> [<nspi-submode>] <subnet>]]",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _run_health() -> None:
    from importlib.metadata import PackageNotFoundError

    result: dict[str, object] = {
        "ok": False,
        "imports": False,
        "version": None,
        "config_readable": False,
        "results_directory_accessible": False,
    }
    try:
        from agent import config  # noqa: F401
        from agent.normalize import contracts  # noqa: F401
        from agent.paths import default_results_dir, load_config
        from agent.scanner import runner  # noqa: F401
        from agent.version import installed_version

        result["imports"] = True
        try:
            result["version"] = installed_version()
        except PackageNotFoundError:
            result["version"] = "unknown"
        configured = load_config()
        result["config_readable"] = True
        directory = Path(
            configured.results_dir if configured is not None else default_results_dir()
        )
        result["results_directory_accessible"] = directory.is_dir() and os.access(
            directory, os.R_OK | os.W_OK
        )
    except Exception:
        pass
    result["ok"] = all(
        result[key]
        for key in ("imports", "config_readable", "results_directory_accessible")
    ) and result["version"] not in (None, "unknown")
    print(json.dumps(result, separators=(",", ":")))
    if not result["ok"]:
        raise SystemExit(20)


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
    if len(args) not in (0, 2, 3):
        _print_agent_usage()
        raise SystemExit(2)

    if len(args) == 3 and args[0] != "nspi":
        _print_agent_usage()
        raise SystemExit(2)

    if not _check_nmap():
        print("Error: nmap is not installed or not on PATH.", file=sys.stderr)
        print("Install nmap: https://nmap.org/download.html", file=sys.stderr)
        raise SystemExit(20)

    if not args:
        from agent.daemon import run_daemon

        run_daemon()
        return

    from agent import headless

    nspi_submode = None
    if len(args) == 3:
        mode, nspi_submode, subnet = args
    else:
        mode, subnet = args
    try:
        result = headless.run_headless_scan(
            mode,
            subnet,
            reporter=headless.StderrReporter(),
            nspi_submode=nspi_submode,
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


def _print_agent_usage() -> None:
    print(
        "Usage: dmitri agent [<mode> [<nspi-submode>] <subnet>]",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
