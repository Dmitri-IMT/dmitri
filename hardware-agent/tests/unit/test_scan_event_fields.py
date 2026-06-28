from __future__ import annotations

import pytest
from agent.scanner.progress import ScanEvent


def test_default_construction_has_zero_skip_accounting() -> None:
    event = ScanEvent(kind="port_stage_done")
    assert event.units_skipped == 0
    assert event.units_total == 0


def test_accepts_skip_accounting_keyword_args() -> None:
    event = ScanEvent(kind="port_stage_done", units_skipped=2, units_total=5)
    assert event.units_skipped == 2
    assert event.units_total == 5


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "hosts_found"},
        {"kind": "port_batch_done", "batches_done": 2, "batches_total": 4},
        {"kind": "host_inspected", "hosts_done": 3, "ip": "10.0.0.2"},
        {"kind": "completed", "message": "done", "ports_open": 7},
    ],
)
def test_existing_style_construction_still_works(kwargs: dict) -> None:
    event = ScanEvent(**kwargs)
    assert event.kind == kwargs["kind"]
    assert event.units_skipped == 0
    assert event.units_total == 0
