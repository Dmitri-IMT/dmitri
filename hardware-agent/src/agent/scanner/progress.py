from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ScanEventKind = Literal[
    "discovery_started",
    "hosts_found",
    "port_stage_started",
    "port_batch_done",
    "port_stage_done",
    "deep_stage_started",
    "host_inspected",
    "deep_stage_done",
    "ot_stage_started",
    "modbus_host_inspected",
    "ot_stage_deadline",
    "ot_stage_done",
    "targeted_stage_started",
    "targeted_unit_done",
    "targeted_stage_done",
    "unit_timed_out",
    "unit_failed",
    "normalize_started",
    "completed",
    "failed",
]


@dataclass(frozen=True, slots=True)
class ScanEvent:
    kind: ScanEventKind
    message: str = ""
    hosts_done: int = 0
    hosts_total: int = 0
    batches_done: int = 0
    batches_total: int = 0
    ports_open: int = 0
    ip: str | None = None
    units_skipped: int = 0
    units_total: int = 0
    units_done: int = 0
    units_completed: int = 0
    units_failed: int = 0
    units_timed_out: int = 0
    outcome: str = ""
    deadline_seconds: int = 0


class ScanReporter(Protocol):
    def emit(self, event: ScanEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class StageWeights:
    discovery: int
    port_scan: int
    deep_inspection: int
    ot_inspection: int
    targeted_assessment: int
    normalize: int


STAGE_WEIGHTS: dict[str, StageWeights] = {
    "quick": StageWeights(15, 50, 30, 0, 0, 5),
    "standard": StageWeights(10, 50, 35, 0, 0, 5),
    "extensive": StageWeights(5, 50, 30, 0, 10, 5),
    "nspi": StageWeights(10, 35, 30, 10, 10, 5),
    "max": StageWeights(5, 50, 30, 0, 10, 5),
}


def target_pct(event: ScanEvent, weights: StageWeights) -> float | None:
    d = float(weights.discovery)
    p = float(weights.port_scan)
    i = float(weights.deep_inspection)
    o = float(weights.ot_inspection)
    t = float(weights.targeted_assessment)

    kind = event.kind
    if kind == "discovery_started":
        return 0.0
    if kind in ("hosts_found", "port_stage_started"):
        return d
    if kind == "port_batch_done":
        fraction = (
            event.batches_done / event.batches_total if event.batches_total else 0.0
        )
        return d + p * fraction
    if kind in ("port_stage_done", "deep_stage_started"):
        return d + p
    if kind == "host_inspected":
        fraction = event.hosts_done / event.hosts_total if event.hosts_total else 0.0
        return d + p + i * fraction
    if kind in ("deep_stage_done", "ot_stage_started"):
        return d + p + i
    if kind == "modbus_host_inspected":
        fraction = event.hosts_done / event.hosts_total if event.hosts_total else 0.0
        return d + p + i + o * fraction
    if kind == "ot_stage_done":
        return d + p + i + o
    if kind == "normalize_started":
        return d + p + i + o + t
    if kind == "targeted_stage_started":
        return d + p + i + o
    if kind == "targeted_unit_done":
        fraction = event.units_done / event.units_total if event.units_total else 0.0
        return d + p + i + o + t * fraction
    if kind == "targeted_stage_done":
        return d + p + i + o + t
    if kind == "completed":
        return 100.0
    return None


class ProgressMapper:
    def __init__(self, scan_mode: str) -> None:
        self._weights = STAGE_WEIGHTS.get(scan_mode, STAGE_WEIGHTS["standard"])
        self._previous = 0.0

    def update(self, event: ScanEvent) -> float:
        target = target_pct(event, self._weights)
        if target is not None and target > self._previous:
            self._previous = target
        return self._previous
