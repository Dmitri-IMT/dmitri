from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from agent.normalize.contracts import (
    HostPayload,
    ModbusTcpServicePayload,
    OpcUaObservationPayload,
    OpcUaPhasePayload,
    OpcUaTcpServicePayload,
    PortPayload,
    ScanPayload,
)
from agent.scanner.live_progress import LiveProgressReporter
from agent.scanner.progress import ScanEvent


def test_reporter_tracks_discovery_port_and_ot_counts_and_throttles() -> None:
    now = [0.0]
    sent = []
    reporter = LiveProgressReporter("nspi", sent.append, clock=lambda: now[0])

    reporter.emit(ScanEvent(kind="discovery_started"))
    reporter.emit(ScanEvent(kind="hosts_found", hosts_total=2))
    reporter.emit(
        ScanEvent(
            kind="port_stage_done",
            ports_open=3,
            ports_filtered=4,
        )
    )

    assert reporter.latest.machines == 2
    assert reporter.latest.open_ports == 3
    assert reporter.latest.filtered_ports == 4
    assert reporter.latest.industrial_services is None
    assert len(sent) == 3

    reporter.emit(ScanEvent(kind="host_inspected", hosts_done=1, hosts_total=2))
    assert len(sent) == 3
    now[0] = 2.1
    reporter.emit(ScanEvent(kind="host_inspected", hosts_done=2, hosts_total=2))
    assert len(sent) == 4

    reporter.emit(ScanEvent(kind="ot_stage_done", industrial_services=5))
    assert reporter.latest.industrial_services == 5
    assert sent[-1].stage == "targeted_assessment"
    assert all(item.percent < 100 for item in sent)
    assert [item.percent for item in sent] == sorted(item.percent for item in sent)


@pytest.mark.parametrize(
    ("scan_mode", "expected_stage"),
    [
        ("quick", "normalization"),
        ("standard", "normalization"),
        ("extensive", "targeted_assessment"),
        ("nspi", "ot_inspection"),
        ("max", "targeted_assessment"),
    ],
)
def test_deep_stage_boundary_maps_to_the_next_stage(
    scan_mode: str, expected_stage: str
) -> None:
    reporter = LiveProgressReporter(scan_mode, lambda _: None, clock=lambda: 0.0)

    reporter.emit(ScanEvent(kind="deep_stage_done"))

    assert reporter.latest.stage == expected_stage


def test_reporter_confirms_empty_discovery_and_non_nspi_industrial_zero() -> None:
    sent = []
    reporter = LiveProgressReporter("quick", sent.append, clock=lambda: 0.0)
    reporter.emit(ScanEvent(kind="hosts_found", hosts_total=0))

    assert reporter.latest.machines == 0
    assert reporter.latest.open_ports == 0
    assert reporter.latest.filtered_ports == 0
    assert reporter.latest.industrial_services == 0
    assert reporter.latest.vulnerabilities is None


def test_payload_reconciliation_replaces_interim_counts_and_caps_progress() -> None:
    sent = []
    reporter = LiveProgressReporter("standard", sent.append, clock=lambda: 0.0)
    reporter.emit(ScanEvent(kind="hosts_found", hosts_total=5))
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(UTC),
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=[
            HostPayload(
                ip="192.168.1.10",
                hostname="camera",
                vendor="Acme",
                ports=[
                    PortPayload(
                        port=80,
                        protocol="tcp",
                        state="open",
                        service="http",
                    ),
                    PortPayload(
                        port=443,
                        protocol="tcp",
                        state="filtered",
                        service="https",
                    ),
                ],
            )
        ],
        findings=[],
    )

    snapshot = reporter.reconcile_payload(payload)

    assert snapshot.stage == "uploading"
    assert snapshot.percent == 99
    assert snapshot.machines == 1
    assert snapshot.open_ports == 1
    assert snapshot.filtered_ports == 1
    assert snapshot.industrial_services == 0
    assert snapshot.vulnerabilities == 0


def test_payload_reconciliation_counts_opcua_services() -> None:
    reporter = LiveProgressReporter("nspi", lambda _: None, clock=lambda: 0.0)
    opcua_service = OpcUaTcpServicePayload(
        protocol="opcua_tcp",
        port=4840,
        confidence="confirmed",
        observation=OpcUaObservationPayload(
            schema_version=1,
            inventory_phase=OpcUaPhasePayload(
                status="completed",
                reason_codes=[],
                truncated=False,
                observed_at=datetime.now(UTC),
            ),
            endpoints=[],
        ),
    )
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(UTC),
        subnet="192.168.1.0/24",
        scan_mode="nspi",
        hosts=[
            HostPayload(
                ip="192.168.1.10",
                hostname="DMITRI",
                vendor="Unknown",
                industrial_services=[opcua_service],
            )
        ],
    )

    snapshot = reporter.reconcile_payload(payload)

    assert snapshot.industrial_services == 1


def test_payload_reconciliation_counts_modbus_and_opcua_once_each() -> None:
    reporter = LiveProgressReporter("nspi", lambda _: None, clock=lambda: 0.0)
    opcua_service = OpcUaTcpServicePayload(
        protocol="opcua_tcp",
        port=4840,
        confidence="confirmed",
        observation=OpcUaObservationPayload(
            schema_version=1,
            inventory_phase=OpcUaPhasePayload(
                status="completed",
                reason_codes=[],
                truncated=False,
                observed_at=datetime.now(UTC),
            ),
            endpoints=[],
        ),
    )
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(UTC),
        subnet="192.168.1.0/24",
        scan_mode="nspi",
        hosts=[
            HostPayload(
                ip="192.168.1.10",
                hostname="PLC",
                vendor="Unknown",
                industrial_services=[
                    ModbusTcpServicePayload(
                        port=502,
                        confidence="confirmed",
                    ),
                    opcua_service,
                ],
            )
        ],
    )

    snapshot = reporter.reconcile_payload(payload)

    assert snapshot.industrial_services == 2
