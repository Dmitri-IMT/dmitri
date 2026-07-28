from __future__ import annotations

from sqlmodel import Session, select

from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
)
from api.schemas.read import SEVERITY_ORDER
from api.schemas.scan import ScanResult


def identity_key(mac: str | None, ip: str) -> str:
    if mac:
        return f"mac:{mac.upper()}"
    return f"ip:{ip}"


def upsert_hosts_for_scan(
    session: Session, scan_record: ScanRecord, scan: ScanResult
) -> None:
    del scan
    scan_host_records = session.exec(
        select(ScanHostRecord).where(ScanHostRecord.scan_id == scan_record.scan_id)
    ).all()

    for sh in scan_host_records:
        key = identity_key(sh.mac, sh.ip)
        host = session.exec(
            select(HostRecord).where(
                HostRecord.org_id.is_not_distinct_from(scan_record.org_id),
                HostRecord.identity_key == key,
            )
        ).first()

        if host is None:
            host = HostRecord(
                org_id=scan_record.org_id,
                identity_key=key,
                ip=sh.ip,
                mac=sh.mac,
                hostname=sh.hostname,
                vendor=sh.vendor,
                open_ports_count=open_ports_count(session, sh.id),
                highest_severity=highest_severity(session, sh.id),
                first_seen_at=scan_record.timestamp,
                last_seen_at=scan_record.timestamp,
            )
            session.add(host)
            session.flush()
        else:
            host.first_seen_at = min(host.first_seen_at, scan_record.timestamp)
            if scan_record.timestamp >= host.last_seen_at:
                host.last_seen_at = scan_record.timestamp
                host.ip = sh.ip
                host.mac = sh.mac
                host.hostname = sh.hostname
                host.vendor = sh.vendor
                host.open_ports_count = open_ports_count(session, sh.id)
                host.highest_severity = highest_severity(session, sh.id)

        sh.host_id = host.id


def open_ports_count(session: Session, scan_host_id: int | None) -> int:
    ports = session.exec(
        select(PortRecord).where(PortRecord.scan_host_id == scan_host_id)
    ).all()
    return sum(1 for port in ports if port.state == "open")


def highest_severity(session: Session, scan_host_id: int | None) -> str | None:
    findings = session.exec(
        select(FindingRecord).where(FindingRecord.scan_host_id == scan_host_id)
    ).all()
    highest: str | None = None
    for finding in findings:
        if highest is None or (
            SEVERITY_ORDER[finding.severity] > SEVERITY_ORDER[highest]
        ):
            highest = finding.severity
    return highest
