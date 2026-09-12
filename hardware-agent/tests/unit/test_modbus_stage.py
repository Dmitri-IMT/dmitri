from __future__ import annotations

from agent.config import AgentSettings
from agent.ot.modbus.models import (
    ModbusDeviceIdentification,
    ModbusService,
    ModbusUnit,
)
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
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
    assert all(host.industrial_services for host in hosts)


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
