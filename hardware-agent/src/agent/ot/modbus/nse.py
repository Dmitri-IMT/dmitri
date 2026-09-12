from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusUnit
from agent.ot.untrusted import bound_objects, bound_text
from agent.scanner.models import ScriptResult

LOGGER = logging.getLogger(__name__)

_UNIT_KEY = re.compile(
    r"(?:^|\b)(?:sid|slave(?:\s+id)?|unit(?:\s+id)?)"
    r"\s*(?:[:=#-]\s*)?(0x[0-9a-f]+|\d+)",
    re.IGNORECASE,
)
_EXCEPTION_CODE = re.compile(r"(?:0x([0-9a-f]+)|\b(\d+)\b)", re.IGNORECASE)
_EXCEPTION_NAMES = {
    "illegal function": 1,
    "illegal data address": 2,
    "illegal data value": 3,
    "slave device failure": 4,
    "acknowledge": 5,
    "slave device busy": 6,
    "memory parity error": 8,
    "gateway path unavailable": 10,
    "gateway target device failed to respond": 11,
    "gateway target device failed to response": 11,
}

_IDENTIFICATION_FIELDS = {
    "vendor": "vendor_name",
    "vendorname": "vendor_name",
    "manufacturer": "vendor_name",
    "productcode": "product_code",
    "majorminorrevision": "major_minor_revision",
    "revision": "major_minor_revision",
    "firmware": "major_minor_revision",
    "vendorurl": "vendor_url",
    "productname": "product_name",
    "model": "model_name",
    "modelname": "model_name",
    "userapplicationname": "user_application_name",
}


class ModbusDiscoverResult(NamedTuple):
    units: list[ModbusUnit]
    parse_failures: int


@dataclass
class _ParseFailures:
    count: int = 0


def parse_modbus_discover(script: ScriptResult) -> ModbusDiscoverResult:
    """Interpret one Nmap modbus-discover result without sending traffic."""

    if script.script_id != "modbus-discover":
        return ModbusDiscoverResult([], 0)

    units: dict[int, ModbusUnit] = {}
    failures = _ParseFailures()
    try:
        _parse_structured(script.data, units, failures=failures)
        _parse_text(script.output, units, failures=failures)
    except (AttributeError, TypeError, ValueError):
        pass
    return ModbusDiscoverResult(
        sorted(units.values(), key=lambda unit: unit.unit_id),
        failures.count,
    )


def _record_unreadable_unit_id(
    key: str,
    raw_value: str,
    failures: _ParseFailures,
) -> None:
    failures.count += 1
    LOGGER.warning("Unreadable Modbus unit id in %s: %s", key, raw_value)


def _parse_structured(
    data: Any,
    units: dict[int, ModbusUnit],
    *,
    failures: _ParseFailures,
) -> None:
    if isinstance(data, Mapping):
        for key, value in data.items():
            match = _UNIT_KEY.search(str(key))
            if match is not None:
                unit_id = _parse_unit_id(match.group(1))
                if unit_id is not None:
                    _merge_unit(units, _unit_from_details(unit_id, value))
                    continue
                _record_unreadable_unit_id(str(key), match.group(1), failures)
            _parse_structured(value, units, failures=failures)
    elif isinstance(data, list):
        for value in data:
            _parse_structured(value, units, failures=failures)


def _parse_text(
    output: str,
    units: dict[int, ModbusUnit],
    *,
    failures: _ParseFailures,
) -> None:
    current_id: int | None = None
    current_key: str | None = None
    details: dict[str, str] = {}

    def flush() -> None:
        nonlocal details
        if current_id is not None:
            _merge_unit(units, _unit_from_details(current_id, details))
        details = {}

    for raw_line in output.splitlines():
        line = raw_line.strip().lstrip("|_").strip()
        unit_match = _UNIT_KEY.search(line)
        if unit_match is not None:
            flush()
            current_key = line
            current_id = _parse_unit_id(unit_match.group(1))
            if current_id is None:
                _record_unreadable_unit_id(
                    current_key or line,
                    unit_match.group(1),
                    failures,
                )
            continue
        if current_id is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() and value.strip():
            details[key.strip()] = value.strip()
    flush()


def _unit_from_details(unit_id: int, details: Any) -> ModbusUnit:
    flattened = _flatten(details)
    exception_code = _find_exception_code(flattened)
    error = _find_error(flattened)
    if error is not None:
        error, _ = bound_text(error)
    identification = _identification_from(flattened)
    return ModbusUnit(
        unit_id=unit_id,
        status="exception" if error is not None else "responding",
        exception_code=exception_code,
        error=error,
        device_identification=identification,
        identification_sources=(
            ["modbus-discover"] if identification is not None else []
        ),
    )


def _flatten(value: Any, prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_key = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten(child, child_key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_key = f"{prefix}[{index}]" if prefix else str(index)
            flattened.update(_flatten(child, child_key))
    elif value is not None:
        flattened[prefix or "value"] = str(value).strip()
    return {key: value for key, value in flattened.items() if value}


def _identification_from(details: dict[str, str]) -> ModbusDeviceIdentification | None:
    identification = ModbusDeviceIdentification()
    truncated = False
    raw_objects: dict[str, str] = {}
    for original_key, value in details.items():
        if _is_error_entry(original_key, value):
            continue
        bounded_value, cut = bound_text(value)
        truncated = truncated or cut
        leaf_key = original_key.rsplit(".", 1)[-1]
        normalized_key = re.sub(r"[^a-z0-9]", "", leaf_key.lower())
        field_name = _IDENTIFICATION_FIELDS.get(normalized_key)
        if field_name is not None:
            setattr(identification, field_name, bounded_value)
        elif bounded_value is not None:
            raw_objects[original_key] = bounded_value
    bounded_objs, dropped = bound_objects(raw_objects)
    identification.objects = bounded_objs
    identification.truncated = truncated or dropped
    if identification.has_structured_fields or identification.objects:
        return identification
    return None


def _find_exception_code(details: dict[str, str]) -> int | None:
    for key, value in details.items():
        if not _is_error_entry(key, value):
            continue
        normalized_value = value.lower()
        for name, code in _EXCEPTION_NAMES.items():
            if name in normalized_value:
                return code
        match = _EXCEPTION_CODE.search(value)
        if match is None:
            continue
        code = int(match.group(1), 16) if match.group(1) else int(match.group(2))
        if 1 <= code <= 255:
            return code
    return None


def _find_error(details: dict[str, str]) -> str | None:
    for key, value in details.items():
        if _is_error_entry(key, value):
            return value
    return None


def _is_error_entry(key: str, value: str) -> bool:
    normalized_key = key.rsplit(".", 1)[-1].lower()
    return normalized_key in {"error", "exception"}


def _parse_unit_id(value: str) -> int | None:
    stripped = value.strip()
    lowered = stripped.lower()
    try:
        if lowered.startswith("0x"):
            unit_id = int(stripped, 16)
        elif lowered.startswith("0b"):
            unit_id = int(stripped, 2)
        elif lowered.startswith("0o"):
            unit_id = int(stripped, 8)
        else:
            unit_id = int(stripped, 10)
    except ValueError:
        return None
    return unit_id if 0 <= unit_id <= 255 else None


def _merge_unit(units: dict[int, ModbusUnit], candidate: ModbusUnit) -> None:
    current = units.get(candidate.unit_id)
    if current is None:
        units[candidate.unit_id] = candidate
        return
    if current.status != "responding" and candidate.status == "responding":
        current.status = "responding"
        current.exception_code = None
    if current.device_identification is None:
        current.device_identification = candidate.device_identification
    elif candidate.device_identification is not None:
        _merge_identification(
            current.device_identification,
            candidate.device_identification,
        )
    for source in candidate.identification_sources:
        if source not in current.identification_sources:
            current.identification_sources.append(source)


def _merge_identification(
    current: ModbusDeviceIdentification,
    candidate: ModbusDeviceIdentification,
) -> None:
    for field_name in _IDENTIFICATION_FIELDS.values():
        if getattr(current, field_name) is None:
            setattr(current, field_name, getattr(candidate, field_name))
    current.objects.update(candidate.objects)
    current.truncated = current.truncated or candidate.truncated
