"""Record builders shared by the read test modules.

The granular ``make_*`` builders are used by ``test_read_service.py`` and
``test_read_service_scans.py``; ``seed_read_graph`` builds the fixed two-org
graph that the ``test_read_hosts/scans/findings/auth`` route modules assert
against. All of it lives here so no module owns another's setup.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from api.models.identity import Org
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
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
    ip: str = "192.168.1.10",
) -> FindingRecord:
    finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan_id,
        scan_host_id=scan_host_id,
        ip=ip,
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


def seed_read_graph(session: Session) -> dict:
    """Seed the fixed graph the read-route modules assert against.

    Two orgs: "Org A" owns one scan, two hosts and two findings; "Org B" owns a
    parallel set that every cross-org test expects to stay invisible.
    """
    now = datetime.now(timezone.utc)

    org = Org(name="Org A")
    session.add(org)
    session.flush()

    other_org = Org(name="Org B")
    session.add(other_org)
    session.flush()

    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org.id,
        timestamp=now,
        subnet="192.168.1.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(scan)
    session.flush()

    host = HostRecord(
        identity_key="aa:bb:cc:dd:ee:ff",
        org_id=org.id,
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        hostname="host-a",
        vendor="Acme",
        open_ports_count=1,
        highest_severity="high",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(host)
    session.flush()

    scan_host = ScanHostRecord(
        scan_id=scan.scan_id,
        host_id=host.id,
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        hostname="host-a",
        vendor="Acme",
    )
    session.add(scan_host)
    session.flush()

    port = PortRecord(
        scan_host_id=scan_host.id,
        port=80,
        protocol="tcp",
        state="open",
    )
    session.add(port)
    session.flush()

    service = ServiceRecord(port_id=port.id, name="http", version="1.0")
    session.add(service)

    finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan.scan_id,
        scan_host_id=scan_host.id,
        ip="192.168.1.10",
        port=80,
        protocol="tcp",
        service="http",
        severity="high",
        title="Vulnerable service",
        description="A vulnerable service was found.",
        recommendation="Patch it.",
        evidence="Some evidence.",
        dedupe_key="dedupe-1",
    )
    session.add(finding)
    session.flush()

    other_host = HostRecord(
        identity_key="11:22:33:44:55:66",
        org_id=org.id,
        ip="192.168.1.20",
        mac="11:22:33:44:55:66",
        hostname="host-b",
        vendor="Acme",
        open_ports_count=1,
        highest_severity="low",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(other_host)
    session.flush()

    other_scan_host = ScanHostRecord(
        scan_id=scan.scan_id,
        host_id=other_host.id,
        ip="192.168.1.20",
        mac="11:22:33:44:55:66",
        hostname="host-b",
        vendor="Acme",
    )
    session.add(other_scan_host)
    session.flush()

    other_finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan.scan_id,
        scan_host_id=other_scan_host.id,
        ip="192.168.1.20",
        port=22,
        protocol="tcp",
        service="ssh",
        severity="low",
        title="Weak cipher",
        description="A weak cipher was found.",
        recommendation="Reconfigure it.",
        evidence="Some evidence.",
        dedupe_key="dedupe-2",
    )
    session.add(other_finding)
    session.flush()

    foreign_scan = ScanRecord(
        scan_id=uuid4(),
        org_id=other_org.id,
        timestamp=now,
        subnet="10.0.0.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(foreign_scan)
    session.flush()

    foreign_host = HostRecord(
        identity_key="ff:ff:ff:ff:ff:ff",
        org_id=other_org.id,
        ip="10.0.0.10",
        mac="ff:ff:ff:ff:ff:ff",
        hostname="host-foreign",
        vendor="Acme",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(foreign_host)
    session.flush()

    foreign_scan_host = ScanHostRecord(
        scan_id=foreign_scan.scan_id,
        host_id=foreign_host.id,
        ip="10.0.0.10",
        mac="ff:ff:ff:ff:ff:ff",
        hostname="host-foreign",
        vendor="Acme",
    )
    session.add(foreign_scan_host)
    session.flush()

    foreign_finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=foreign_scan.scan_id,
        scan_host_id=foreign_scan_host.id,
        ip="10.0.0.10",
        port=443,
        protocol="tcp",
        service="https",
        severity="low",
        title="Foreign finding",
        description="Belongs to another org.",
        recommendation="N/A",
        evidence="N/A",
        dedupe_key="dedupe-foreign",
    )
    session.add(foreign_finding)
    session.commit()

    return {
        "org": org,
        "other_org": other_org,
        "scan": scan,
        "host": host,
        "finding": finding,
        "other_host": other_host,
        "other_finding": other_finding,
        "foreign_scan": foreign_scan,
        "foreign_host": foreign_host,
        "foreign_finding": foreign_finding,
    }
