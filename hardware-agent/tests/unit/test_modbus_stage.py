from __future__ import annotations

import threading
import time
from time import perf_counter

from agent.config import AgentSettings
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.ot.policy import MAX_OT_HOST_SECONDS, MAX_OT_STAGE_SECONDS, min_not_none
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo, StageCoverage
from agent.scanner.stages import (
    build_host_payload,
    build_metadata,
    run_ot_inspection_stage,
)


class _Reporter:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


class _Runner:
    nmap_path = "nmap"


def _service() -> ModbusService:
    return ModbusService(
        port=502,
        confidence="confirmed",
        evidence_sources=["modbus-discover", "pymodbus"],
        units=[
            ModbusUnit(
                unit_id=7,
                status="responding",
                device_identification=ModbusDeviceIdentification(
                    vendor_name="ACME",
                    product_code="PLC-7",
                    major_minor_revision="1.0",
                ),
            )
        ],
        requests_sent=1,
    )


def test_ot_stage_runs_only_for_nspi_and_is_serial(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip="192.168.10.30",
            hostname="plc-a",
            ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        ),
        HostInfo(
            ip="192.168.10.31",
            hostname="plc-b",
            ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        ),
    ]
    calls = []

    def fake_inventory(host, **kwargs):
        calls.append(host.ip)
        return [_service()]

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", fake_inventory)
    reporter = _Reporter()

    run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi"),
        hosts,
        reporter=reporter,
    )

    assert calls == ["192.168.10.30", "192.168.10.31"]
    assert [event.kind for event in reporter.events] == [
        "ot_stage_started",
        "modbus_host_inspected",
        "modbus_host_inspected",
        "ot_stage_done",
    ]
    assert reporter.events[-1].industrial_services == 2
    assert all(host.industrial_services for host in hosts)
    assert all(
        host.stage_coverage
        == [
            StageCoverage(
                "ot_inspection", "completed", "modbus_inspection", None,
                502, "tcp", "modbus"
            )
        ]
        for host in hosts
    )


def test_non_nspi_ot_stage_is_noop(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502)],
    )
    monkeypatch.setattr(
        "agent.scanner.stages.inventory_modbus_host",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    run_ot_inspection_stage(AgentSettings(scan_mode="standard"), [host])

    assert host.industrial_services == []


def test_inventory_serialises_to_host_payload_and_metadata() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[_service()],
    )

    payload = build_host_payload(host)
    metadata = build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=None,
        elapsed_seconds=1.0,
        hosts_discovered=1,
        findings_count=0,
        hosts=[host],
    )

    assert payload.industrial_services[0].units[0].unit_id == 7
    identification = payload.industrial_services[0].units[0].device_identification
    assert identification is not None
    assert identification.vendor_name == "ACME"
    assert metadata["nspi_submode"] == "inventory"
    assert metadata["modbus_candidates"] == 1
    assert metadata["modbus_confirmed"] == 1
    assert metadata["modbus_units"] == 1
    assert metadata["modbus_requests_sent"] == 1
    assert metadata["modbus_write_requests_sent"] == 0


def test_host_payload_preserves_service_cpes_for_backend_enrichment() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[
            PortInfo(
                port=502,
                service=ServiceInfo(
                    name="modbus",
                    cpes=[
                        "cpe:2.3:o:schneider-electric:"
                        "modicon_m340_firmware:2.60:*:*:*:*:*:*:*"
                    ],
                ),
            )
        ],
    )

    payload = build_host_payload(host)

    assert payload.ports[0].cpes == host.ports[0].service.cpes


def test_read_only_mapping_dispatches_after_inventory(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
    )
    mapped = []
    monkeypatch.setattr(
        "agent.scanner.stages.inventory_modbus_host",
        lambda *args, **kwargs: [_service()],
    )

    def fake_map(host_arg, service, **kwargs):
        mapped.append((host_arg.ip, service.port, kwargs["policy"].version))

    monkeypatch.setattr("agent.scanner.stages.map_modbus_service", fake_map)

    run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"),
        [host],
    )

    assert mapped == [("192.168.10.30", 502, 1)]


def test_inventory_submode_never_dispatches_mapping(monkeypatch) -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
    )
    monkeypatch.setattr(
        "agent.scanner.stages.inventory_modbus_host",
        lambda *args, **kwargs: [_service()],
    )
    monkeypatch.setattr(
        "agent.scanner.stages.map_modbus_service",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    run_ot_inspection_stage(AgentSettings(scan_mode="nspi"), [host])


def test_ot_stage_cancel_does_not_emit_deadline() -> None:
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
    )
    cancel_event = threading.Event()
    cancel_event.set()
    reporter = _Reporter()

    ot_inspection = run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi"),
        [host],
        reporter=reporter,
        cancel_event=cancel_event,
    )

    assert not ot_inspection.stage_deadline_reached
    assert ot_inspection.stage_deadline_seconds is None
    assert host.stage_coverage == [
        StageCoverage("ot_inspection", "skipped", "modbus_inspection", "scan_cancelled")
    ]
    assert not any(event.kind == "ot_stage_deadline" for event in reporter.events)
    assert "modbus_stage_deadline_reached" not in build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=None,
        elapsed_seconds=1.0,
        hosts_discovered=1,
        findings_count=0,
        hosts=[host],
        ot_inspection=ot_inspection,
    )


def test_ot_stage_deadline_emits_event_and_metadata(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip=f"192.168.10.{index}",
            hostname=f"plc-{index}",
            ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        )
        for index in (30, 31, 32)
    ]
    monkeypatch.setattr("agent.scanner.stages.MAX_OT_STAGE_SECONDS", 0)

    def slow_inventory(host, **kwargs):
        time.sleep(0.02)
        return [_service()]

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", slow_inventory)
    reporter = _Reporter()

    ot_inspection = run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi"),
        hosts,
        reporter=reporter,
    )

    deadline_events = [
        event for event in reporter.events if event.kind == "ot_stage_deadline"
    ]
    assert len(deadline_events) == 1
    assert (
        "Time limit reached during industrial inspection" in deadline_events[0].message
    )
    assert deadline_events[0].units_skipped >= 1
    assert all(len(host.stage_coverage) == 1 for host in hosts)
    assert StageCoverage(
        "ot_inspection", "skipped", "modbus_inspection", "stage_budget"
    ) in [host.stage_coverage[0] for host in hosts]

    metadata = build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=None,
        elapsed_seconds=1.0,
        hosts_discovered=len(hosts),
        findings_count=0,
        hosts=hosts,
        partial_result=False,
        ot_inspection=ot_inspection,
    )
    assert metadata["industrial_stage_deadline_reached"] is True
    assert metadata["industrial_stage_deadline_seconds"] == 1
    assert metadata["partial_result"] is False


def test_ot_host_deadline_allows_remaining_hosts(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip=f"192.168.10.{index}",
            hostname=f"plc-{index}",
            ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        )
        for index in (30, 31)
    ]
    monkeypatch.setattr("agent.scanner.stages.MAX_OT_HOST_SECONDS", 0)

    def slow_inventory(host, **kwargs):
        time.sleep(0.02)
        return [_service()]

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", slow_inventory)
    reporter = _Reporter()

    ot_inspection = run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi"),
        hosts,
        reporter=reporter,
    )

    inspected = [
        event for event in reporter.events if event.kind == "modbus_host_inspected"
    ]
    assert len(inspected) == 2
    assert all(host.industrial_services for host in hosts)
    assert all(
        host.stage_coverage
        == [
            StageCoverage(
                    "ot_inspection", "completed", "modbus_inspection", None,
                    502, "tcp", "modbus"
            )
        ]
        for host in hosts
    )
    assert not any(event.kind == "ot_stage_deadline" for event in reporter.events)

    metadata = build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=None,
        elapsed_seconds=1.0,
        hosts_discovered=len(hosts),
        findings_count=0,
        hosts=hosts,
        ot_inspection=ot_inspection,
    )
    assert "modbus_stage_deadline_reached" not in metadata


def test_write_counter_comes_from_service_field() -> None:
    service = _service()
    service.write_requests_sent = 3
    host = HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        industrial_services=[service],
    )

    metadata = build_metadata(
        runner=_Runner(),
        settings=AgentSettings(scan_mode="nspi"),
        network_info=None,
        elapsed_seconds=1.0,
        hosts_discovered=1,
        findings_count=0,
        hosts=[host],
    )

    assert metadata["modbus_write_requests_sent"] == 3


def test_mapping_deadline_counts_host_that_started(monkeypatch) -> None:
    hosts = [
        HostInfo(
            ip=f"192.168.10.{index}",
            hostname=f"plc-{index}",
            ports=[PortInfo(port=502, service=ServiceInfo(name="modbus"))],
        )
        for index in (30, 31)
    ]
    monkeypatch.setattr("agent.scanner.stages.MAX_OT_STAGE_SECONDS", 0)

    def slow_inventory(host, **kwargs):
        time.sleep(0.02)
        return [_service()]

    mapped: list[str] = []

    def fake_map(host, service, **kwargs):
        mapped.append(host.ip)

    monkeypatch.setattr("agent.scanner.stages.inventory_modbus_host", slow_inventory)
    monkeypatch.setattr("agent.scanner.stages.map_modbus_service", fake_map)
    reporter = _Reporter()

    ot_inspection = run_ot_inspection_stage(
        AgentSettings(scan_mode="nspi", nspi_submode="read_only_mapping"),
        hosts,
        reporter=reporter,
    )

    inspected = [
        event.hosts_done
        for event in reporter.events
        if event.kind == "modbus_host_inspected"
    ]
    deadline_events = [
        event for event in reporter.events if event.kind == "ot_stage_deadline"
    ]
    assert ot_inspection.stage_deadline_reached
    assert len(deadline_events) == 1
    assert inspected == list(range(1, len(inspected) + 1))
    assert deadline_events[0].units_skipped == len(hosts) - len(inspected)
    assert mapped == [host.ip for host in hosts[: len(inspected)]]


def test_default_ot_deadline_constants_are_non_none() -> None:
    now = perf_counter()
    stage_deadline = min_not_none(None, now + MAX_OT_STAGE_SECONDS)
    host_deadline = min_not_none(stage_deadline, now + MAX_OT_HOST_SECONDS)
    assert stage_deadline is not None
    assert host_deadline is not None
    assert host_deadline <= stage_deadline
