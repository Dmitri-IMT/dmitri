from __future__ import annotations

import struct
import threading

from agent.ot.modbus.inventory import inventory_modbus_host
from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusUnit
from agent.ot.policy import OtAutomationPolicy
from agent.scanner.models import HostInfo, PortInfo, ScriptResult, ServiceInfo


def _host(port: PortInfo) -> HostInfo:
    return HostInfo(ip="192.168.10.30", hostname="plc-lab", ports=[port])


def test_complete_nse_identification_prevents_duplicate_fc43() -> None:
    port = PortInfo(
        port=502,
        service=ServiceInfo(name="modbus"),
        scripts=[
            ScriptResult(
                script_id="modbus-discover",
                data={
                    "sid 1": {
                        "VendorName": "Schneider Electric",
                        "ProductCode": "BMX P34",
                        "MajorMinorRevision": "2.60",
                    }
                },
            )
        ],
    )
    probe_calls = []

    services = inventory_modbus_host(
        _host(port),
        probe=lambda *args, **kwargs: probe_calls.append((args, kwargs)),
    )

    assert probe_calls == []
    assert len(services) == 1
    assert services[0].confidence == "confirmed"
    assert services[0].evidence_sources == [
        "tcp-port",
        "nmap-service",
        "modbus-discover",
    ]
    assert services[0].requests_sent == 0
    assert services[0].units[0].unit_id == 1


def test_fc43_enriches_unit_found_by_nse() -> None:
    port = PortInfo(
        port=502,
        service=ServiceInfo(name="mbap"),
        scripts=[
            ScriptResult(
                script_id="modbus-discover",
                data={"sid 0x07": {"Slave ID data": "PLC-LAB"}},
            )
        ],
    )
    probe_calls = []

    def probe(host, port_number, unit_id, *, timeout):
        probe_calls.append((host, port_number, unit_id, timeout))
        return ModbusUnit(
            unit_id=unit_id,
            status="responding",
            device_identification=ModbusDeviceIdentification(
                vendor_name="ACME",
                product_code="PLC-7",
            ),
        )

    service = inventory_modbus_host(
        _host(port), timeout=0.75, probe=probe, sleep=lambda _: None
    )[0]

    assert probe_calls == [("192.168.10.30", 502, 7, 0.75)]
    assert service.requests_sent == 1
    assert service.units[0].device_identification is not None
    assert service.units[0].device_identification.vendor_name == "ACME"
    assert service.units[0].device_identification.objects == {
        "Slave ID data": "PLC-LAB"
    }


def test_open_502_uses_only_bounded_unit_one_fallback() -> None:
    port = PortInfo(port=502, service=ServiceInfo(name="unknown"))
    probe_calls = []

    def probe(host, port_number, unit_id, *, timeout):
        probe_calls.append(unit_id)
        return ModbusUnit(unit_id=unit_id, status="timeout")

    service = inventory_modbus_host(
        _host(port), probe=probe, sleep=lambda _: None
    )[0]

    assert probe_calls == [1]
    assert service.confidence == "suspected"
    assert service.requests_sent == 1
    assert service.timeouts == 1
    assert service.units[0].status == "timeout"


def test_non_modbus_port_and_cancelled_scan_send_no_requests() -> None:
    calls = []
    non_modbus = _host(PortInfo(port=80, service=ServiceInfo(name="http")))
    assert inventory_modbus_host(
        non_modbus,
        probe=lambda *args, **kwargs: calls.append(args),
    ) == []

    cancel_event = threading.Event()
    cancel_event.set()
    modbus = _host(PortInfo(port=502, service=ServiceInfo(name="modbus")))
    assert inventory_modbus_host(
        modbus,
        cancel_event=cancel_event,
        probe=lambda *args, **kwargs: calls.append(args),
    ) == []
    assert calls == []


def test_struct_error_on_one_unit_preserves_sibling_units() -> None:
    port = PortInfo(
        port=502,
        service=ServiceInfo(name="modbus"),
        scripts=[
            ScriptResult(
                script_id="modbus-discover",
                data={
                    "sid 1": {"Slave ID data": "u1"},
                    "sid 2": {"Slave ID data": "u2"},
                    "sid 3": {"Slave ID data": "u3"},
                    "sid 4": {"Slave ID data": "u4"},
                },
            )
        ],
    )

    def probe(host, port_number, unit_id, *, timeout, **kwargs):
        if unit_id == 3:
            raise struct.error("unpack requires a buffer of 4 bytes")
        return ModbusUnit(
            unit_id=unit_id,
            status="responding",
            device_identification=ModbusDeviceIdentification(vendor_name="ACME"),
        )

    service = inventory_modbus_host(
        _host(port),
        probe=probe,
        sleep=lambda _: None,
    )[0]
    by_id = {unit.unit_id: unit for unit in service.units}

    assert set(by_id) == {1, 2, 3, 4}
    assert by_id[1].status == "responding"
    assert by_id[2].status == "responding"
    assert by_id[4].status == "responding"
    assert by_id[3].status == "error"
    assert by_id[3].error == struct.error.__name__


def test_identification_probes_sleep_before_each_fc43() -> None:
    policy = OtAutomationPolicy(inter_request_delay_ms=250)
    sleeps: list[float] = []
    port = PortInfo(
        port=502,
        service=ServiceInfo(name="modbus"),
        scripts=[
            ScriptResult(
                script_id="modbus-discover",
                data={
                    "sid 1": {"Slave ID data": "u1"},
                    "sid 2": {"Slave ID data": "u2"},
                    "sid 3": {"Slave ID data": "u3"},
                    "sid 4": {"Slave ID data": "u4"},
                },
            )
        ],
    )
    probe_calls: list[int] = []

    def probe(host, port_number, unit_id, *, timeout, **kwargs):
        probe_calls.append(unit_id)
        return ModbusUnit(unit_id=unit_id, status="responding")

    inventory_modbus_host(
        _host(port),
        policy=policy,
        probe=probe,
        sleep=sleeps.append,
    )

    assert probe_calls == [1, 2, 3, 4]
    assert sleeps == [0.25, 0.25, 0.25, 0.25]
