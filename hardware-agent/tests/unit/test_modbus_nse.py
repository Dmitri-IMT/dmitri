from __future__ import annotations

from agent.ot.modbus.nse import parse_modbus_discover
from agent.scanner.models import ScriptResult


def test_parses_structured_units_and_identification() -> None:
    script = ScriptResult(
        script_id="modbus-discover",
        data={
            "sid 0x01": {
                "VendorName": "Schneider Electric",
                "ProductCode": "BMX P34",
                "MajorMinorRevision": "2.60",
            },
            "sid 0x64": {"Slave ID data": "gateway-device"},
        },
    )

    units = parse_modbus_discover(script)

    assert [unit.unit_id for unit in units] == [1, 100]
    assert units[0].status == "responding"
    assert units[0].device_identification is not None
    assert units[0].device_identification.vendor_name == "Schneider Electric"
    assert units[0].device_identification.product_code == "BMX P34"
    assert units[0].device_identification.major_minor_revision == "2.60"
    assert units[1].device_identification is not None
    assert units[1].device_identification.objects == {
        "Slave ID data": "gateway-device"
    }


def test_text_fallback_preserves_unit_and_raw_device_identification() -> None:
    script = ScriptResult(
        script_id="modbus-discover",
        output="""
        sid 0x64:
          Slave ID data: PLC-LAB
          Device identification: ACME controller 1.0
        """,
    )

    units = parse_modbus_discover(script)

    assert len(units) == 1
    assert units[0].unit_id == 100
    assert units[0].status == "responding"
    assert units[0].device_identification is not None
    assert units[0].device_identification.objects["Device identification"] == (
        "ACME controller 1.0"
    )


def test_exception_is_preserved() -> None:
    script = ScriptResult(
        script_id="modbus-discover",
        data={"Unit ID 7": {"Exception": "Illegal data address (code 0x02)"}},
    )

    units = parse_modbus_discover(script)

    assert len(units) == 1
    assert units[0].unit_id == 7
    assert units[0].status == "exception"
    assert units[0].exception_code == 2


def test_real_nmap_gateway_error_name_maps_to_exception_code() -> None:
    script = ScriptResult(
        script_id="modbus-discover",
        output="""
        sid 0x96:
          error: GATEWAY TARGET DEVICE FAILED TO RESPONSE
        """,
        data={
            "sid 0x96": {
                "error": "GATEWAY TARGET DEVICE FAILED TO RESPONSE",
            }
        },
    )

    units = parse_modbus_discover(script)

    assert len(units) == 1
    assert units[0].unit_id == 150
    assert units[0].status == "exception"
    assert units[0].exception_code == 11
    assert units[0].error == "GATEWAY TARGET DEVICE FAILED TO RESPONSE"
    assert units[0].device_identification is None


def test_malformed_and_unrelated_scripts_are_safe() -> None:
    malformed = ScriptResult(
        script_id="modbus-discover",
        output="sid not-a-number:\nDevice identification:",
        data={"sid 999": object()},
    )
    unrelated = ScriptResult(script_id="vulners", data={"sid 1": "not Modbus"})

    assert parse_modbus_discover(malformed) == []
    assert parse_modbus_discover(unrelated) == []
