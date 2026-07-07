from __future__ import annotations

import ipaddress
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent import config
from agent.normalize.contracts import ScanPayload
from agent.paths import default_results_dir, load_config
from agent.scanner.nmap import NmapRunner
from agent.scanner.progress import ScanEvent, ScanReporter
from agent.tui.results import write_scan_result
from agent.tui.scanner import ScanRunner


class InvalidScanInput(ValueError):
    pass


@dataclass(slots=True)
class HeadlessScanResult:
    outcome: Literal["completed", "partial", "fatal"]
    payload: ScanPayload | None
    result_path: Path | None
    error: Exception | None


EXIT_CODES: dict[str, int] = {"completed": 0, "partial": 10, "fatal": 20}
INVALID_INPUT_EXIT = 2


class StderrReporter:
    def emit(self, event: ScanEvent) -> None:
        print(event.message, file=sys.stderr)


def validate_inputs(mode: str, subnet: str) -> None:
    if mode not in config.SCAN_MODES:
        raise InvalidScanInput(
            f"Unknown scan mode {mode!r}; must be one of {config.SCAN_MODES}"
        )
    if "/" not in subnet:
        raise InvalidScanInput(
            f"Subnet {subnet!r} must be CIDR notation, e.g. 192.168.1.0/24"
        )
    try:
        ipaddress.IPv4Network(subnet, strict=False)
    except ValueError as exc:
        raise InvalidScanInput(f"Invalid subnet {subnet!r}: {exc}") from exc


def _resolve_workspace_root(workspace_root: Path | None) -> Path:
    if workspace_root is not None:
        return workspace_root
    dmitri_config = load_config()
    if dmitri_config is not None:
        return Path(dmitri_config.results_dir)
    return Path(default_results_dir())


def run_headless_scan(
    mode: str,
    subnet: str,
    *,
    workspace_root: Path | None = None,
    reporter: ScanReporter | None = None,
    runner: NmapRunner | None = None,
) -> HeadlessScanResult:
    validate_inputs(mode, subnet)

    workspace_root = _resolve_workspace_root(workspace_root)
    try:
        (workspace_root / "results").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return HeadlessScanResult(
            outcome="fatal", payload=None, result_path=None, error=exc
        )

    captured_payload: ScanPayload | None = None
    captured_error: Exception | None = None

    def _on_complete(payload: ScanPayload) -> None:
        nonlocal captured_payload
        captured_payload = payload

    def _on_error(error: Exception) -> None:
        nonlocal captured_error
        captured_error = error

    scan_runner = ScanRunner(
        subnet,
        mode,
        reporter=reporter,
        on_complete=_on_complete,
        on_error=_on_error,
        workspace_root=workspace_root,
        runner=runner,
    )
    scan_runner.run_blocking()

    if captured_payload is not None:
        result_path = write_scan_result(captured_payload, str(workspace_root))
        partial = bool(
            captured_payload.metadata
            and captured_payload.metadata.get("partial_result")
        )
        outcome: Literal["completed", "partial"] = (
            "partial" if partial else "completed"
        )
        return HeadlessScanResult(
            outcome=outcome,
            payload=captured_payload,
            result_path=result_path,
            error=None,
        )

    return HeadlessScanResult(
        outcome="fatal", payload=None, result_path=None, error=captured_error
    )
