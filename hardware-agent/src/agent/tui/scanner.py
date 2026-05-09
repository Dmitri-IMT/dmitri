"""TUI scan runner — worker thread, cancellation, progress reporting."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent.config import AgentSettings
from agent.normalize.contracts import ScanPayload
from agent.scanner.pipeline import ScanOrchestrator
from agent.utils.network import LocalNetworkInfo, check_network_connectivity


class ScanCancelled(Exception):
    """Raised when the scan is aborted by the user."""


@dataclass(slots=True)
class ProgressSnapshot:
    """A stage transition report sent to the UI."""

    stage: str
    detail: str = ""
    completed: bool = False


StageType = Literal[
    "discovery", "port_scan", "deep_inspection", "normalizing", "completed"
]


class ScanRunner:
    """Owns the worker thread and cancel event for a single scan session."""

    def __init__(
        self,
        subnet: str,
        scan_mode: Literal["quick", "full"],
        on_progress: Callable[[ProgressSnapshot], None] | None = None,
        on_complete: Callable[[ScanPayload], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        self.subnet = subnet
        self.scan_mode = scan_mode
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error
        self._workspace_root = workspace_root
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _check_cancel(self) -> None:
        if self._cancel_event.is_set():
            raise ScanCancelled()

    def _emit(self, stage: str, detail: str = "", *, completed: bool = False) -> None:
        if self._on_progress:
            self._on_progress(
                ProgressSnapshot(stage=stage, detail=detail, completed=completed)
            )

    def _run(self) -> None:
        try:
            check_network_connectivity()
            settings = AgentSettings(
                scan_subnet=self.subnet,
                scan_mode=self.scan_mode,
            )
            network_info = LocalNetworkInfo(
                ip="0.0.0.0",
                netmask="255.255.255.0",
                subnet=self.subnet,
                interface="tui",
            )
            orchestrator = ScanOrchestrator(
                settings, workspace_root=self._workspace_root
            )
            orchestrator.network_info = network_info

            self._emit("discovery")
            self._check_cancel()
            orchestrator.current_stage = "discovery"
            orchestrator._set_runner_stage("discovery")
            from agent.discovery.network_discovery import discover_hosts

            orchestrator.hosts = discover_hosts(orchestrator.runner, self.subnet)
            self._check_cancel()

            hosts_count = len(orchestrator.hosts)
            self._emit("discovery", f"({hosts_count} hosts found)", completed=True)

            self._emit("port_scan")
            if orchestrator.hosts:
                self._check_cancel()
                orchestrator._run_port_stage(orchestrator.hosts)
                self._check_cancel()

                total_ports = sum(len(h.ports) for h in orchestrator.hosts)
                self._emit(
                    "port_scan",
                    f"Ports open: {total_ports}",
                    completed=True,
                )

                self._emit("deep_inspection")
                orchestrator._run_deep_inspection_stage(orchestrator.hosts)
                self._check_cancel()
                self._emit("deep_inspection", "Done", completed=True)
            else:
                self._emit("port_scan", "(no hosts)", completed=True)
                self._emit("deep_inspection")
                self._emit("deep_inspection", "(skipped)", completed=True)

            self._emit("normalizing")
            self._check_cancel()
            from agent.normalize.findings import extract_findings

            findings = extract_findings(orchestrator.hosts)

            from datetime import datetime, timezone

            orchestrator.current_stage = "completed"
            devices = [
                orchestrator._build_device_payload(h) for h in orchestrator.hosts
            ]
            payload = ScanPayload(
                scan_id=orchestrator.scan_id,
                timestamp=datetime.now(timezone.utc),
                subnet=self.subnet,
                scan_mode=self.scan_mode,
                devices=devices,
                findings=findings,
                metadata=orchestrator._build_metadata(
                    elapsed_seconds=0,
                    hosts_discovered=hosts_count,
                    findings_count=len(findings),
                ),
            )

            final_ports = sum(len(d.ports) for d in devices)
            self._emit(
                "normalizing",
                f"Ports: {final_ports} | Vulnerabilities: {len(findings)}",
                completed=True,
            )

            self._check_cancel()
            self._emit("completed", "DONE!")
            if self._on_complete:
                self._on_complete(payload)

        except ScanCancelled:
            pass
        except Exception as exc:
            if self._on_error:
                self._on_error(exc)
