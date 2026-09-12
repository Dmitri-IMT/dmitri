from __future__ import annotations

from agent.ot.modbus.models import ModbusDeviceIdentification, ModbusUnit

_STATUS_RANK = {
    "responding": 4,
    "exception": 3,
    "timeout": 2,
    "error": 2,
    "skipped": 1,
}


def merge_unit(units: dict[int, ModbusUnit], candidate: ModbusUnit) -> None:
    current = units.get(candidate.unit_id)
    if current is None:
        units[candidate.unit_id] = candidate
        return

    if _STATUS_RANK[candidate.status] > _STATUS_RANK[current.status]:
        current.status = candidate.status
        current.exception_code = candidate.exception_code
        current.error = candidate.error

    if candidate.device_identification is not None:
        if current.device_identification is None:
            current.device_identification = candidate.device_identification
        else:
            merge_identification(
                current.device_identification,
                candidate.device_identification,
            )
    for source in candidate.identification_sources:
        if source not in current.identification_sources:
            current.identification_sources.append(source)


def merge_identification(
    current: ModbusDeviceIdentification,
    candidate: ModbusDeviceIdentification,
) -> None:
    for field_name in (
        "vendor_name",
        "product_code",
        "major_minor_revision",
        "vendor_url",
        "product_name",
        "model_name",
        "user_application_name",
    ):
        if getattr(current, field_name) is None:
            setattr(current, field_name, getattr(candidate, field_name))
    current.objects.update(candidate.objects)
    current.truncated = current.truncated or candidate.truncated
