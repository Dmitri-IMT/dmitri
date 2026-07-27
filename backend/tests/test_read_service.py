from __future__ import annotations

import inspect
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
from api.services import read
from sqlmodel import Session


def _make_org(session: Session, name: str) -> Org:
    org = Org(name=name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _make_host(session: Session, org_id, ip: str) -> HostRecord:
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


def _make_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.1.0/24",
        scan_mode="quick",
        status="completed",
        metadata_json={},
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def _make_scan_host(
    session: Session, scan_id, host_id, ip: str
) -> ScanHostRecord:
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


def _make_finding(
    session: Session, scan_id, scan_host_id, dedupe_key: str
) -> FindingRecord:
    finding = FindingRecord(
        finding_id=uuid4(),
        scan_id=scan_id,
        scan_host_id=scan_host_id,
        ip="192.168.1.10",
        port=80,
        protocol="tcp",
        service="http",
        severity="high",
        title="Vulnerable service",
        description="A vulnerable service was found.",
        recommendation="Patch it.",
        evidence="Some evidence.",
        dedupe_key=dedupe_key,
    )
    session.add(finding)
    session.commit()
    session.refresh(finding)
    return finding


def test_org_id_is_keyword_only_and_required_on_all_four_functions() -> None:
    for target in (
        read.list_hosts,
        read.get_host_detail,
        read.get_scan_detail,
        read.list_findings,
    ):
        param = inspect.signature(target).parameters["org_id"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is inspect.Parameter.empty


def test_list_hosts_scopes_count_and_page_by_org(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    _make_host(administrative_session, org_a.id, "192.168.1.10")
    _make_host(administrative_session, org_a.id, "192.168.1.11")
    _make_host(administrative_session, org_b.id, "192.168.1.20")

    result_a = read.list_hosts(administrative_session, org_id=org_a.id)
    assert result_a.total == 2
    assert {str(row.ip) for row in result_a.data} == {"192.168.1.10", "192.168.1.11"}

    result_b = read.list_hosts(administrative_session, org_id=org_b.id)
    assert result_b.total == 1
    assert {str(row.ip) for row in result_b.data} == {"192.168.1.20"}


def test_get_host_detail_returns_none_for_foreign_org(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    host = _make_host(administrative_session, org_a.id, "192.168.1.10")

    assert read.get_host_detail(
        administrative_session, host.id, org_id=org_b.id
    ) is None
    assert (
        read.get_host_detail(administrative_session, host.id, org_id=org_a.id)
        is not None
    )


def test_get_host_detail_scopes_scan_history_and_ports_to_own_org(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    host = _make_host(administrative_session, org_a.id, "192.168.1.10")
    foreign_scan = _make_scan(administrative_session, org_b.id)
    scan_host = _make_scan_host(
        administrative_session, foreign_scan.scan_id, host.id, host.ip
    )
    port = PortRecord(
        scan_host_id=scan_host.id, port=80, protocol="tcp", state="open"
    )
    administrative_session.add(port)
    administrative_session.commit()
    administrative_session.refresh(port)
    administrative_session.add(
        ServiceRecord(port_id=port.id, name="http", version="1.0")
    )
    administrative_session.commit()

    detail = read.get_host_detail(administrative_session, host.id, org_id=org_a.id)

    assert detail is not None
    assert detail.scan_history == []
    assert detail.ports == []


def test_get_host_detail_shows_own_org_scan_but_not_foreign(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    host = _make_host(administrative_session, org_a.id, "192.168.1.10")
    own_scan = _make_scan(administrative_session, org_a.id)
    foreign_scan = _make_scan(administrative_session, org_b.id)
    own_scan_host = _make_scan_host(
        administrative_session, own_scan.scan_id, host.id, host.ip
    )
    foreign_scan_host = _make_scan_host(
        administrative_session, foreign_scan.scan_id, host.id, host.ip
    )
    own_port = PortRecord(
        scan_host_id=own_scan_host.id, port=443, protocol="tcp", state="open"
    )
    foreign_port = PortRecord(
        scan_host_id=foreign_scan_host.id, port=22, protocol="tcp", state="open"
    )
    administrative_session.add(own_port)
    administrative_session.add(foreign_port)
    administrative_session.commit()

    detail = read.get_host_detail(administrative_session, host.id, org_id=org_a.id)

    assert detail is not None
    assert {entry.scan_id for entry in detail.scan_history} == {own_scan.scan_id}
    assert {p.port for p in detail.ports} == {443}


def test_get_scan_detail_returns_none_for_foreign_org(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    scan = _make_scan(administrative_session, org_a.id)

    assert (
        read.get_scan_detail(administrative_session, scan.scan_id, org_id=org_b.id)
        is None
    )
    assert (
        read.get_scan_detail(administrative_session, scan.scan_id, org_id=org_a.id)
        is not None
    )


def test_list_findings_scopes_count_and_page_by_org(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    org_b = _make_org(administrative_session, "Org B")
    host_a = _make_host(administrative_session, org_a.id, "192.168.1.10")
    host_b = _make_host(administrative_session, org_b.id, "192.168.1.20")
    scan_a = _make_scan(administrative_session, org_a.id)
    scan_b = _make_scan(administrative_session, org_b.id)
    scan_host_a = _make_scan_host(
        administrative_session, scan_a.scan_id, host_a.id, host_a.ip
    )
    scan_host_b = _make_scan_host(
        administrative_session, scan_b.scan_id, host_b.id, host_b.ip
    )
    finding_a = _make_finding(
        administrative_session, scan_a.scan_id, scan_host_a.id, "dedupe-a"
    )
    _make_finding(administrative_session, scan_b.scan_id, scan_host_b.id, "dedupe-b")

    result_a = read.list_findings(administrative_session, org_id=org_a.id)
    assert result_a.total == 1
    assert result_a.data[0].finding_id == finding_a.finding_id

    result_a_by_host = read.list_findings(
        administrative_session, org_id=org_a.id, host_id=host_a.id
    )
    assert result_a_by_host.total == 1

    result_a_by_foreign_host = read.list_findings(
        administrative_session, org_id=org_a.id, host_id=host_b.id
    )
    assert result_a_by_foreign_host.total == 0


def test_null_org_id_host_and_scan_visible_to_nobody(
    administrative_session: Session,
) -> None:
    org_a = _make_org(administrative_session, "Org A")
    orphan_host = _make_host(administrative_session, None, "192.168.1.30")
    orphan_scan = _make_scan(administrative_session, None)

    assert (
        read.get_host_detail(
            administrative_session, orphan_host.id, org_id=org_a.id
        )
        is None
    )
    assert (
        read.get_scan_detail(
            administrative_session, orphan_scan.scan_id, org_id=org_a.id
        )
        is None
    )
    result = read.list_hosts(administrative_session, org_id=org_a.id)
    assert orphan_host.id not in {row.host_id for row in result.data}
