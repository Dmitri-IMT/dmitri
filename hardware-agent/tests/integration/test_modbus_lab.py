from __future__ import annotations

from agent.ot.modbus.client import probe_device_identification
from agent.ot.modbus.inventory import inventory_modbus_host
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.scanner.stages import build_host_payload
from pymodbus.client import ModbusTcpClient

from tests.fixtures.modbus_lab import ModbusLabServer


def test_inventory_fc43_against_deterministic_lab_target() -> None:
    with ModbusLabServer() as lab:
        unit = probe_device_identification(
            lab.host,
            lab.port,
            lab.unit_id,
            timeout=1.0,
        )

    assert unit.status == "responding"
    assert unit.device_identification is not None
    assert unit.device_identification.vendor_name == "Dmitri Laboratory"
    assert unit.device_identification.product_code == "MODBUS-TARGET"
    assert unit.device_identification.major_minor_revision == "1.0"
    assert unit.device_identification.model_name == "LAB-PLC"


def test_lab_target_has_four_spaces_illegal_ranges_and_resettable_write_points() -> (
    None
):
    with ModbusLabServer() as lab:
        client = ModbusTcpClient(lab.host, port=lab.port, timeout=1.0, retries=0)
        assert client.connect() is True
        try:
            coils = client.read_coils(0, count=4, device_id=lab.unit_id)
            discrete = client.read_discrete_inputs(0, count=4, device_id=lab.unit_id)
            holding = client.read_holding_registers(0, count=4, device_id=lab.unit_id)
            inputs = client.read_input_registers(0, count=4, device_id=lab.unit_id)
            illegal = client.read_holding_registers(
                500,
                count=1,
                device_id=lab.unit_id,
            )

            assert coils.bits[:4] == [False, True, False, True]
            assert discrete.bits[:4] == [True, False, True, False]
            assert holding.registers == [0, 7, 42, 1450]
            assert inputs.registers == [10, 20, 30, 40]
            assert illegal.isError() is True

            original = client.read_holding_registers(
                100,
                count=1,
                device_id=lab.unit_id,
            ).registers[0]
            assert original == 0
            write_result = client.write_register(100, 1, device_id=lab.unit_id)
            assert write_result.isError() is False
            changed = client.read_holding_registers(
                100,
                count=1,
                device_id=lab.unit_id,
            ).registers[0]
            assert changed == 1
            assert (
                client.write_register(100, original, device_id=lab.unit_id).isError()
                is False
            )
        finally:
            client.close()


def test_inventory_round_trips_from_lab_target_to_json_contract() -> None:
    with ModbusLabServer() as lab:
        host = HostInfo(
            ip=lab.host,
            hostname="modbus-lab",
            ports=[
                PortInfo(
                    port=lab.port,
                    service=ServiceInfo(name="modbus"),
                )
            ],
        )
        host.industrial_services = inventory_modbus_host(host, timeout=1.0)
        payload = build_host_payload(host)

    dumped = payload.model_dump(mode="json")
    service = dumped["industrial_services"][0]
    identification = service["units"][0]["device_identification"]
    assert service["protocol"] == "modbus_tcp"
    assert service["confidence"] == "confirmed"
    assert identification["vendor_name"] == "Dmitri Laboratory"
    assert identification["product_code"] == "MODBUS-TARGET"
