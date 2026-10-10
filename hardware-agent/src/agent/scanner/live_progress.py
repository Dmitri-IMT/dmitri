from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from time import monotonic
from typing import Literal

from agent.config import TARGETED_MODES
from agent.normalize.contracts import ScanPayload
from agent.scanner.progress import ProgressMapper, ScanEvent, ScanReporter

ProgressStage = Literal[
    "discovery",
    "ports",
    "deep_inspection",
    "ot_inspection",
    "targeted_assessment",
    "normalization",
    "uploading",
]

_IMMEDIATE_EVENTS = frozenset(
    {
        "discovery_started",
        "hosts_found",
        "port_stage_started",
        "port_stage_done",
        "deep_stage_started",
        "deep_stage_done",
        "ot_stage_started",
        "ot_stage_done",
        "targeted_stage_started",
        "targeted_stage_done",
        "normalize_started",
        "completed",
    }
)
_MIN_REPORT_INTERVAL_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class LiveProgressSnapshot:
    stage: ProgressStage
    percent: int
    machines: int | None = None
    open_ports: int | None = None
    filtered_ports: int | None = None
    industrial_services: int | None = None
    vulnerabilities: int | None = None
    revision: int = 0


class LiveProgressReporter(ScanReporter):
    """Turn internal scan events into throttled, compact remote snapshots."""

    def __init__(
        self,
        scan_mode: str,
        on_update: Callable[[LiveProgressSnapshot], None],
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._mapper = ProgressMapper(scan_mode)
        self._scan_mode = scan_mode
        self._on_update = on_update
        self._clock = clock
        self._last_reported_at = float("-inf")
        self._snapshot = LiveProgressSnapshot(
            stage="discovery",
            percent=0,
            industrial_services=0 if scan_mode != "nspi" else None,
        )

    @property
    def latest(self) -> LiveProgressSnapshot:
        return self._snapshot

    def emit(self, event: ScanEvent) -> None:
        stage = _stage_for(event.kind, self._snapshot.stage, self._scan_mode)
        percent = min(99, int(self._mapper.update(event)))
        changes: dict[str, object] = {"stage": stage, "percent": percent}
        if event.kind == "hosts_found":
            changes["machines"] = event.hosts_total
            if event.hosts_total == 0:
                changes["open_ports"] = 0
                changes["filtered_ports"] = 0
        elif event.kind == "port_stage_done":
            changes["open_ports"] = event.ports_open
            changes["filtered_ports"] = event.ports_filtered
        elif event.kind == "ot_stage_done":
            changes["industrial_services"] = event.industrial_services

        self._snapshot = replace(self._snapshot, **changes)
        self._snapshot = replace(self._snapshot, revision=self._snapshot.revision + 1)
        now = self._clock()
        if (
            event.kind in _IMMEDIATE_EVENTS
            or now - self._last_reported_at >= _MIN_REPORT_INTERVAL_SECONDS
        ):
            self._publish(now)

    def reconcile_payload(self, payload: ScanPayload) -> LiveProgressSnapshot:
        """Replace interim counts with the normalized result before upload."""
        self._snapshot = replace(
            self._snapshot,
            stage="uploading",
            percent=99,
            machines=len(payload.hosts),
            open_ports=sum(
                port.state == "open" for host in payload.hosts for port in host.ports
            ),
            filtered_ports=sum(
                port.state == "filtered"
                for host in payload.hosts
                for port in host.ports
            ),
            industrial_services=sum(
                len(host.industrial_services) for host in payload.hosts
            ),
            vulnerabilities=len(payload.findings),
            revision=self._snapshot.revision + 1,
        )
        return self._snapshot

    def publish_latest(self) -> None:
        self._publish(self._clock())

    def _publish(self, now: float) -> None:
        self._last_reported_at = now
        self._on_update(self._snapshot)


def _stage_for(kind: str, previous: ProgressStage, scan_mode: str) -> ProgressStage:
    if kind in {"discovery_started", "hosts_found"}:
        return "discovery" if kind == "discovery_started" else "ports"
    if kind in {"port_stage_started", "port_batch_done"}:
        return "ports"
    if kind in {"port_stage_done", "deep_stage_started", "host_inspected"}:
        return "deep_inspection"
    if kind == "deep_stage_done":
        return (
            "targeted_assessment"
            if scan_mode in TARGETED_MODES and scan_mode != "nspi"
            else "ot_inspection" if scan_mode == "nspi" else "normalization"
        )
    if kind in {"ot_stage_started", "modbus_host_inspected"}:
        return "ot_inspection"
    if kind == "ot_stage_done":
        return "targeted_assessment" if scan_mode == "nspi" else "normalization"
    if kind in {"targeted_stage_started", "targeted_unit_done"}:
        return "targeted_assessment"
    if kind in {"targeted_stage_done", "normalize_started", "completed"}:
        return "normalization"
    return previous
