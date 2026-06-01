"""TUI scan runner — worker thread, cancellation, progress reporting."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

from agent.config import AgentSettings, min_cvss_for_mode
from agent.discovery.network_discovery import discover_hosts
from agent.normalize.contracts import ScanPayload
from agent.normalize.findings import extract_findings
from agent.scanner import stages
from agent.scanner.nmap import NmapRunner, build_runner
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
        scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"],
        on_progress: Callable[[ProgressSnapshot], None] | None = None,
        on_complete: Callable[[ScanPayload], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        workspace_root: Path | None = None,
        runner: NmapRunner | None = None,
    ) -> None:
        self.subnet = subnet
        self.scan_mode = scan_mode
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error
        self._workspace_root = workspace_root
        self._runner = runner
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
                min_cvss=min_cvss_for_mode(self.scan_mode),
            )
            network_info = LocalNetworkInfo(
                ip="0.0.0.0",
                netmask="255.255.255.0",
                subnet=self.subnet,
                interface="tui",
            )
            scan_id = uuid4()
            runner = build_runner(
                settings,
                self._workspace_root,
                scan_id,
                runner=self._runner,
            )

            started_counter = perf_counter()

            self._emit("discovery")
            self._check_cancel()
            stages.set_runner_stage(runner, "discovery")
            hosts = discover_hosts(runner, self.subnet)
            self._check_cancel()

            hosts_count = len(hosts)
            self._emit("discovery", f"({hosts_count} hosts found)", completed=True)

            self._emit("port_scan")
            if hosts:
                self._check_cancel()
                stages.run_port_stage(runner, settings, hosts)
                self._check_cancel()

                total_ports = sum(len(h.ports) for h in hosts)
                self._emit(
                    "port_scan",
                    f"Ports open: {total_ports}",
                    completed=True,
                )

                self._emit("deep_inspection")
                stages.run_deep_inspection_stage(runner, settings, hosts)
                self._check_cancel()
                self._emit("deep_inspection", "Done", completed=True)
            else:
                self._emit("port_scan", "(no hosts)", completed=True)
                self._emit("deep_inspection")
                self._emit("deep_inspection", "(skipped)", completed=True)

            self._emit("normalizing")
            self._check_cancel()
            findings = extract_findings(hosts)
            elapsed_seconds = round(perf_counter() - started_counter, 2)
            devices = [stages.build_device_payload(h) for h in hosts]
            payload = ScanPayload(
                scan_id=scan_id,
                timestamp=datetime.now(timezone.utc),
                subnet=self.subnet,
                scan_mode=self.scan_mode,
                devices=devices,
                findings=findings,
                metadata=stages.build_metadata(
                    runner=runner,
                    settings=settings,
                    network_info=network_info,
                    elapsed_seconds=elapsed_seconds,
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
