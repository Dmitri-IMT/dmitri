from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from api.core.machine_type import classify_machine_type
from api.models.persistence import (
    FindingRecord,
    HostFindingRecord,
    HostPortRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)


def reconcile_scan_inventory(session: Session, scan_record: ScanRecord) -> None:
    scan_hosts = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_record.scan_id)
    ).all()
    for scan_host in scan_hosts:
        host = _host_for(session, scan_host)
        if host is not None:
            _reconcile_machine(session, scan_record, scan_host, host)


def reconcile_scan_host_inventory(session: Session, scan_host: ScanHostRecord) -> None:
    host = _host_for(session, scan_host)
    scan_record = session.get(ScanRecord, scan_host.scan_id)
    if host is None or scan_record is None:
        return
    _reconcile_machine(session, scan_record, scan_host, host)


def _host_for(session: Session, scan_host: ScanHostRecord) -> HostRecord | None:
    if scan_host.host_id is None:
        return None
    return session.get(HostRecord, scan_host.host_id)


def _reconcile_machine(
    session: Session,
    scan_record: ScanRecord,
    scan_host: ScanHostRecord,
    host: HostRecord,
) -> None:
    ts = scan_record.timestamp
    is_latest = ts >= host.last_seen_at

    open_services = _reconcile_ports(session, host, scan_host, ts, is_latest)
    findings = _reconcile_findings(
        session, host, scan_record, scan_host, ts, is_latest
    )

    if is_latest:
        host.machine_type = classify_machine_type(scan_host.vendor, open_services)
        host.vulnerability_count = sum(
            1 for row in findings if row.fixed_at is None
        )
        session.add(host)
    session.flush()


def _reconcile_ports(
    session: Session,
    host: HostRecord,
    scan_host: ScanHostRecord,
    ts: datetime,
    is_latest: bool,
) -> list[tuple[int, str]]:
    rows = session.exec(
        select(PortRecord, ServiceRecord)
        .join(ServiceRecord, ServiceRecord.port_id == PortRecord.id)
        .where(
            PortRecord.scan_host_id == scan_host.id,
            PortRecord.state == "open",
        )
    ).all()
    known = {
        (row.port, row.protocol): row
        for row in session.exec(
            select(HostPortRecord).where(HostPortRecord.host_id == host.id)
        ).all()
    }

    open_services: list[tuple[int, str]] = []
    for port, service in rows:
        open_services.append((port.port, service.name))
        existing = known.get((port.port, port.protocol))
        if existing is None:
            known[(port.port, port.protocol)] = HostPortRecord(
                host_id=host.id,
                port=port.port,
                protocol=port.protocol,
                service=service.name,
                version=service.version,
                first_seen_at=ts,
                last_seen_at=ts,
            )
            session.add(known[(port.port, port.protocol)])
            continue
        existing.first_seen_at = min(existing.first_seen_at, ts)
        if is_latest:
            existing.last_seen_at = ts
            existing.service = service.name
            existing.version = service.version
        session.add(existing)
    return open_services


def _reconcile_findings(
    session: Session,
    host: HostRecord,
    scan_record: ScanRecord,
    scan_host: ScanHostRecord,
    ts: datetime,
    is_latest: bool,
) -> list[HostFindingRecord]:
    """Apply this scan's findings to the machine's finding life.

    Returns every `host_findings` row for the machine after the scan is applied.
    """
    seen = set(
        session.exec(
            select(FindingRecord.dedupe_key).where(
                FindingRecord.scan_id == scan_record.scan_id,
                FindingRecord.scan_host_id == scan_host.id,
            )
        ).all()
    )
    known = {
        row.dedupe_key: row
        for row in session.exec(
            select(HostFindingRecord).where(HostFindingRecord.host_id == host.id)
        ).all()
    }

    for dedupe_key in seen:
        existing = known.get(dedupe_key)
        if existing is None:
            known[dedupe_key] = HostFindingRecord(
                host_id=host.id,
                dedupe_key=dedupe_key,
                first_seen_at=ts,
                last_seen_at=ts,
                fixed_at=None,
            )
            session.add(known[dedupe_key])
            continue
        existing.first_seen_at = min(existing.first_seen_at, ts)
        if is_latest:
            existing.last_seen_at = ts
            existing.fixed_at = None
        session.add(existing)

    if is_latest:
        for row in known.values():
            if row.dedupe_key not in seen and row.fixed_at is None:
                row.fixed_at = ts
                session.add(row)
    return list(known.values())
