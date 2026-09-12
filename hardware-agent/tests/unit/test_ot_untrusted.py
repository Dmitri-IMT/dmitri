from __future__ import annotations

from agent.ot.modbus.nse import parse_modbus_discover
from agent.ot.untrusted import (
    MAX_DEVICE_STRING_CHARS,
    MAX_IDENTIFICATION_OBJECTS,
    bound_objects,
    bound_text,
)
from agent.scanner.models import ScriptResult


def test_bound_text_truncates_at_128_chars() -> None:
    long_value = "a" * 129
    bounded, truncated = bound_text(long_value)

    assert len(bounded or "") == MAX_DEVICE_STRING_CHARS
    assert truncated is True


def test_bound_objects_caps_at_16_objects() -> None:
    objects = {str(index): f"value-{index}" for index in range(17)}
    bounded, truncated = bound_objects(objects)

    assert len(bounded) == MAX_IDENTIFICATION_OBJECTS
    assert truncated is True


def test_identification_truncated_flag_reflects_bounds() -> None:
    script = ScriptResult(
        script_id="modbus-discover",
        data={"sid 1": {"VendorName": "x" * 129, "extra-0": "y" * 129}},
    )

    result = parse_modbus_discover(script)

    identification = result.units[0].device_identification
    assert identification is not None
    assert identification.truncated is True
    assert len(identification.vendor_name or "") == MAX_DEVICE_STRING_CHARS
    assert len(identification.objects["extra-0"]) == MAX_DEVICE_STRING_CHARS
