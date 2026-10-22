from __future__ import annotations

from sqlmodel import Session, select

from api.models.persistence import (
    IndustrialServiceRecord,
    ModbusUnitRecord,
    PortRecord,
)
from api.schemas.industrial import (
    IndustrialServicePayload,
    ModbusTcpServicePayload,
    ModbusUnitPayload,
    OpcUaTcpServicePayload,
)


def _apply_service_fields(
    record: IndustrialServiceRecord,
    service: ModbusTcpServicePayload,
    *,
    port_record: PortRecord | None,
) -> None:
    record.port_id = port_record.id if port_record is not None else record.port_id
    record.confidence = service.confidence
    record.mapping_source = service.mapping_source
    record.evidence_sources_json = list(service.evidence_sources)
    record.write_requests_sent = service.write_requests_sent


def _apply_unit_fields(record: ModbusUnitRecord, unit: ModbusUnitPayload) -> None:
    record.status = unit.status
    record.exception_code = unit.exception_code
    record.error = unit.error
    record.identification_json = (
        unit.device_identification.model_dump(mode="json", exclude_none=True)
        if unit.device_identification is not None
        else None
    )
    record.identification_sources_json = list(unit.identification_sources)
    record.address_ranges_json = [
        range_payload.model_dump(mode="json", exclude_none=True)
        for range_payload in unit.address_ranges
    ]


def persist_industrial_services(
    session: Session,
    scan_host_id: int,
    services: list[IndustrialServicePayload],
    *,
    port_index: dict[tuple[int, str], PortRecord],
) -> dict[tuple[int, int], ModbusUnitRecord]:
    """Persist industrial observations for one scan host.

    Returns a map of ``(service_port, unit_id)`` to the persisted unit row.
    Idempotent on ``(scan_host_id, protocol, port)`` and
    ``(industrial_service_id, unit_id)``.
    """
    existing_services = {
        (service.protocol, service.port): service
        for service in session.exec(
            select(IndustrialServiceRecord).where(
                IndustrialServiceRecord.scan_host_id == scan_host_id
            )
        ).all()
    }
    port_by_service_id = {
        service.id: service.port for service in existing_services.values()
    }
    service_ids = list(port_by_service_id)
    existing_units: dict[tuple[int, int], ModbusUnitRecord] = {}
    if service_ids:
        for unit in session.exec(
            select(ModbusUnitRecord).where(
                ModbusUnitRecord.industrial_service_id.in_(service_ids)
            )
        ).all():
            port = port_by_service_id.get(unit.industrial_service_id)
            if port is not None:
                existing_units[(port, unit.unit_id)] = unit

    for service in services:
        port_record = port_index.get((service.port, "tcp"))
        service_key = (service.protocol, service.port)
        service_record = existing_services.get(service_key)
        if service_record is None:
            is_modbus = isinstance(service, ModbusTcpServicePayload)
            service_record = IndustrialServiceRecord(
                scan_host_id=scan_host_id,
                port_id=port_record.id if port_record is not None else None,
                protocol=service.protocol,
                port=service.port,
                confidence=service.confidence,
                mapping_source=service.mapping_source if is_modbus else None,
                evidence_sources_json=list(service.evidence_sources),
                write_requests_sent=service.write_requests_sent,
                opcua_observation_json=(
                    service.observation.model_dump(mode="json")
                    if isinstance(service, OpcUaTcpServicePayload)
                    else None
                ),
            )
            session.add(service_record)
            existing_services[service_key] = service_record
        else:
            if isinstance(service, ModbusTcpServicePayload):
                _apply_service_fields(service_record, service, port_record=port_record)
                service_record.opcua_observation_json = None
            else:
                if port_record is not None:
                    service_record.port_id = port_record.id
                service_record.confidence = service.confidence
                service_record.mapping_source = None
                service_record.evidence_sources_json = list(service.evidence_sources)
                service_record.write_requests_sent = service.write_requests_sent
                service_record.opcua_observation_json = service.observation.model_dump(
                    mode="json"
                )
            session.add(service_record)

    session.flush()

    unit_index: dict[tuple[int, int], ModbusUnitRecord] = {}
    for service in services:
        if not isinstance(service, ModbusTcpServicePayload):
            continue
        service_record = existing_services[(service.protocol, service.port)]
        for unit in service.units:
            unit_record = existing_units.get((service.port, unit.unit_id))
            if unit_record is None:
                unit_record = ModbusUnitRecord(
                    industrial_service_id=service_record.id,
                    unit_id=unit.unit_id,
                )
                session.add(unit_record)
                existing_units[(service.port, unit.unit_id)] = unit_record
            _apply_unit_fields(unit_record, unit)
            session.add(unit_record)
            unit_index[(service.port, unit.unit_id)] = unit_record

    session.flush()
    return unit_index


def industrial_services_for_scan_host(
    session: Session, scan_host_id: int
) -> list[IndustrialServiceRecord]:
    return list(
        session.exec(
            select(IndustrialServiceRecord).where(
                IndustrialServiceRecord.scan_host_id == scan_host_id
            )
        ).all()
    )
