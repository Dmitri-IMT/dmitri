"""Record builders shared by the read-service test modules.

``test_read_service.py`` and ``test_read_service_scans.py`` both seed the same
five tables; these live here so neither module owns the other's setup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from api.models.identity import Org
from api.models.persistence import FindingRecord, HostRecord, ScanHostRecord, ScanRecord
from sqlmodel import Session


def make_org(session: Session, name: str) -> Org:
    org = Org(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def make_host(session: Session, org_id, ip: str) -> HostRecord:
    now = datetime.now(timezone.utc)
    host = HostRecord(
        org_id=org_id,
        identity_key=f"identity-{ip}",
        ip=ip,
        mac=f"aa:bb:cc:dd:ee:{len(ip):02x}",
        hostname="host",
        vendor="vendor",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(host)
    session.commit()
    session.refresh(host)
    return host


def make_scan(
    session: Session,
    org_id,
    *,
    timestamp: datetime | None = None,
    status: str = "completed",
    scan_mode: str = "quick",
    subnet: str = "192.168.1.0/24",
) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        subnet=subnet,
        scan_mode=scan_mode,
        status=status,
        metadata_json={},
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def make_scan_host(session: Session, scan_id, host_id, ip: str) -> ScanHostRecord:
    scan_host = ScanHostRecord(
        scan_id=scan_id,
        host_id=host_id,
        ip=ip,
        mac=None,
        hostname="host",
        vendor="vendor",
    )
    session.add(scan_host)
    session.commit()
    session.refresh(scan_host)
    return scan_host


def make_finding(
    session: Session,
    scan_id,
    scan_host_id,
    dedupe_key: str,
    *,
    severity: str = "high",
    created_at: datetime | None = None,
) -> FindingRecord:
    finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan_id,
        scan_host_id=scan_host_id,
        ip="192.168.1.10",
        port=80,
        protocol="tcp",
        service="http",
        severity=severity,
        title="Vulnerable service",
        description="A vulnerable service was found.",
        recommendation="Patch it.",
        evidence="Some evidence.",
        dedupe_key=dedupe_key,
    )
    if created_at is not None:
        finding.created_at = created_at
        finding.updated_at = created_at
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return finding
