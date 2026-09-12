from __future__ import annotations

from sqlmodel import Session, select

from api.models.persistence import (
    IndustrialServiceRecord,
    ModbusUnitRecord,
    PortRecord,
)
from api.schemas.industrial import ModbusTcpServicePayload


def persist_industrial_services(
    session: Session,
    scan_host_id: int,
    services: list[ModbusTcpServicePayload],
    *,
    port_index: dict[tuple[int, str], PortRecord],
) -> dict[tuple[int, int], ModbusUnitRecord]:
    """Persist industrial observations for one scan host.

    Returns a map of ``(service_port, unit_id)`` to the persisted unit row.
    Idempotent on ``(scan_host_id, protocol, port)`` and
    ``(industrial_service_id, unit_id)``.
    """
    unit_index: dict[tuple[int, int], ModbusUnitRecord] = {}
    for service in services:
        port_record = port_index.get((service.port, "tcp"))
        service_record = session.exec(
            select(IndustrialServiceRecord).where(
                IndustrialServiceRecord.scan_host_id == scan_host_id,
                IndustrialServiceRecord.protocol == service.protocol,
                IndustrialServiceRecord.port == service.port,
            )
        ).first()
        if service_record is None:
            service_record = IndustrialServiceRecord(
                scan_host_id=scan_host_id,
                port_id=port_record.id if port_record is not None else None,
                protocol=service.protocol,
                port=service.port,
                confidence=service.confidence,
                mapping_source=service.mapping_source,
                evidence_sources_json=list(service.evidence_sources),
                write_requests_sent=service.write_requests_sent,
            )
            session.add(service_record)
            session.flush()
        else:
            service_record.port_id = (
                port_record.id if port_record is not None else service_record.port_id
            )
            service_record.confidence = service.confidence
            service_record.mapping_source = service.mapping_source
            service_record.evidence_sources_json = list(service.evidence_sources)
            service_record.write_requests_sent = service.write_requests_sent
            session.add(service_record)
            session.flush()

        for unit in service.units:
            unit_record = session.exec(
                select(ModbusUnitRecord).where(
                    ModbusUnitRecord.industrial_service_id == service_record.id,
                    ModbusUnitRecord.unit_id == unit.unit_id,
                )
            ).first()
            identification_json = (
                unit.device_identification.model_dump(mode="json", exclude_none=True)
                if unit.device_identification is not None
                else None
            )
            address_ranges_json = [
                range_payload.model_dump(mode="json", exclude_none=True)
                for range_payload in unit.address_ranges
            ]
            if unit_record is None:
                unit_record = ModbusUnitRecord(
                    industrial_service_id=service_record.id,
                    unit_id=unit.unit_id,
                    status=unit.status,
                    exception_code=unit.exception_code,
                    error=unit.error,
                    identification_json=identification_json,
                    identification_sources_json=list(unit.identification_sources),
                    address_ranges_json=address_ranges_json,
                )
                session.add(unit_record)
            else:
                unit_record.status = unit.status
                unit_record.exception_code = unit.exception_code
                unit_record.error = unit.error
                unit_record.identification_json = identification_json
                unit_record.identification_sources_json = list(
                    unit.identification_sources
                )
                unit_record.address_ranges_json = address_ranges_json
                session.add(unit_record)
            session.flush()
            unit_index[(service.port, unit.unit_id)] = unit_record

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
