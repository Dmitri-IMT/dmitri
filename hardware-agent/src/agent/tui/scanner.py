"""TUI scan runner — worker thread, cancellation, progress reporting."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

from agent.config import AgentSettings, min_cvss_for_mode, subprocess_timeout_for
from agent.discovery.network_discovery import discover_hosts
from agent.normalize.contracts import ScanPayload
from agent.normalize.findings import extract_findings
from agent.scanner import stages
from agent.scanner.errors import (
    BudgetExceeded,
    CircuitBreakerError,
    FatalScanError,
    ScanCancelled,
)
from agent.scanner.nmap import NmapRunner, build_runner
from agent.scanner.progress import ScanEvent, ScanReporter
from agent.utils.network import LocalNetworkInfo, check_network_connectivity


class ScanRunner:
    """Owns the worker thread and cancel event for a single scan session."""

    def __init__(
        self,
        subnet: str,
        scan_mode: Literal["quick", "standard", "extensive", "nspi", "max"],
        reporter: ScanReporter | None = None,
        on_complete: Callable[[ScanPayload], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        workspace_root: Path | None = None,
        runner: NmapRunner | None = None,
    ) -> None:
        self.subnet = subnet
        self.scan_mode = scan_mode
        self._reporter = reporter
        self._on_complete = on_complete
        self._on_error = on_error
        self._workspace_root = workspace_root
        self._runner = runner
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._runner_lock = threading.Lock()
        self._active_runner: NmapRunner | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_cancel(self) -> None:
        self._cancel_event.set()
        with self._runner_lock:
            runner = self._active_runner
        if runner is not None:
            runner.terminate_active()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _check_cancel(self) -> None:
        if self._cancel_event.is_set():
            raise ScanCancelled()

    def _check_deadline(self, deadline: float | None) -> None:
        if deadline is not None and perf_counter() >= deadline:
            raise BudgetExceeded()

    def _emit(self, event: ScanEvent) -> None:
        if self._reporter is not None:
            self._reporter.emit(event)

    def _build_payload(
        self,
        *,
        scan_id,
        settings: AgentSettings,
        network_info: LocalNetworkInfo,
        runner: NmapRunner,
        started_counter: float,
        hosts: list,
        partial_result: bool,
        interrupted_stage: str | None,
        terminated_by: str,
    ) -> ScanPayload:
        findings = extract_findings(hosts)
        elapsed_seconds = round(perf_counter() - started_counter, 2)
        devices = [stages.build_device_payload(h) for h in hosts]
        return ScanPayload(
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
                hosts_discovered=len(hosts),
                findings_count=len(findings),
                partial_result=partial_result,
                interrupted_stage=interrupted_stage,
                terminated_by=terminated_by,
            ),
        )

    def _finalize_partial(
        self,
        *,
        scan_id,
        settings: AgentSettings | None,
        network_info: LocalNetworkInfo | None,
        runner: NmapRunner | None,
        started_counter: float | None,
        hosts: list,
        interrupted_stage: str | None,
        terminated_by: str,
        message: str,
    ) -> None:
        if (
            runner is None
            or settings is None
            or network_info is None
            or started_counter is None
        ):
            self._emit(ScanEvent(kind="failed", message=message))
            return
        try:
            payload = self._build_payload(
                scan_id=scan_id,
                settings=settings,
                network_info=network_info,
                runner=runner,
                started_counter=started_counter,
                hosts=hosts,
                partial_result=True,
                interrupted_stage=interrupted_stage,
                terminated_by=terminated_by,
            )
        except Exception as exc:
            self._emit(ScanEvent(kind="failed", message=message))
            if self._on_error:
                self._on_error(exc)
            return
        if not hosts:
            self._emit(ScanEvent(kind="failed", message=message))
        if self._on_complete:
            self._on_complete(payload)

    def _run(self) -> None:
        settings: AgentSettings | None = None
        network_info: LocalNetworkInfo | None = None
        runner: NmapRunner | None = None
        started_counter: float | None = None
        scan_id = uuid4()
        hosts: list = []
        interrupted_stage: str | None = "discovery"
        discovery_done = False
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
            runner = build_runner(
                settings,
                self._workspace_root,
                scan_id,
                runner=self._runner,
            )
            with self._runner_lock:
                self._active_runner = runner

            started_counter = perf_counter()
            deadline = (
                started_counter + settings.scan_deadline_s
                if settings.scan_deadline_s > 0
                else None
            )

            self._emit(ScanEvent(kind="discovery_started", message="Finding hosts…"))
            self._check_cancel()
            stages.set_runner_stage(runner, "discovery")
            hosts = discover_hosts(
                runner,
                self.subnet,
                timeout=subprocess_timeout_for(self.scan_mode, "discovery"),
            )
            discovery_done = True
            self._check_cancel()
            self._check_deadline(deadline)

            hosts_count = len(hosts)
            self._emit(
                ScanEvent(
                    kind="hosts_found",
                    message=(
                        f"{hosts_count} hosts found"
                        if hosts_count
                        else "No hosts found"
                    ),
                    hosts_total=hosts_count,
                )
            )

            interrupted_stage = None
            if hosts:
                interrupted_stage = "ports"
                self._check_cancel()
                self._check_deadline(deadline)
                stages.run_port_stage(
                    runner,
                    settings,
                    hosts,
                    reporter=self._reporter,
                    cancel_event=self._cancel_event,
                )
                self._check_cancel()
                self._check_deadline(deadline)

                interrupted_stage = "deep_inspection"
                stages.run_deep_inspection_stage(
                    runner,
                    settings,
                    hosts,
                    reporter=self._reporter,
                    cancel_event=self._cancel_event,
                )
                self._check_cancel()
                self._check_deadline(deadline)

            interrupted_stage = "normalize"
            self._emit(
                ScanEvent(kind="normalize_started", message="Generating results…")
            )
            self._check_cancel()
            payload = self._build_payload(
                scan_id=scan_id,
                settings=settings,
                network_info=network_info,
                runner=runner,
                started_counter=started_counter,
                hosts=hosts,
                partial_result=False,
                interrupted_stage=None,
                terminated_by="completed",
            )

            self._check_cancel()
            self._emit(ScanEvent(kind="completed", message="Done"))
            if self._on_complete:
                self._on_complete(payload)

        except FatalScanError as exc:
            if not discovery_done:
                self._emit(ScanEvent(kind="failed", message=f"Scan failed: {exc}"))
                if self._on_error:
                    self._on_error(exc)
            else:
                self._finalize_partial(
                    scan_id=scan_id,
                    settings=settings,
                    network_info=network_info,
                    runner=runner,
                    started_counter=started_counter,
                    hosts=hosts,
                    interrupted_stage=interrupted_stage,
                    terminated_by="error",
                    message=f"Scan failed: {exc}",
                )
        except BudgetExceeded as exc:
            if isinstance(exc, CircuitBreakerError):
                self._finalize_partial(
                    scan_id=scan_id,
                    settings=settings,
                    network_info=network_info,
                    runner=runner,
                    started_counter=started_counter,
                    hosts=hosts,
                    interrupted_stage=interrupted_stage,
                    terminated_by="error",
                    message="Scan stopped early",
                )
            else:
                self._finalize_partial(
                    scan_id=scan_id,
                    settings=settings,
                    network_info=network_info,
                    runner=runner,
                    started_counter=started_counter,
                    hosts=hosts,
                    interrupted_stage=interrupted_stage,
                    terminated_by="timeout",
                    message="Scan timed out",
                )
        except ScanCancelled:
            self._finalize_partial(
                scan_id=scan_id,
                settings=settings,
                network_info=network_info,
                runner=runner,
                started_counter=started_counter,
                hosts=hosts,
                interrupted_stage=interrupted_stage,
                terminated_by="user_cancel",
                message="Scan aborted",
            )
        except Exception as exc:
            if discovery_done and hosts:
                self._finalize_partial(
                    scan_id=scan_id,
                    settings=settings,
                    network_info=network_info,
                    runner=runner,
                    started_counter=started_counter,
                    hosts=hosts,
                    interrupted_stage=interrupted_stage,
                    terminated_by="error",
                    message=f"Scan failed: {exc}",
                )
            else:
                self._emit(ScanEvent(kind="failed", message=f"Scan failed: {exc}"))
                if self._on_error:
                    self._on_error(exc)
        finally:
            with self._runner_lock:
                self._active_runner = None
