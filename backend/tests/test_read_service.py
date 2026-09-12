from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from api.models.identity import Org
from api.models.persistence import (
    FindingRecord,
    HostPortRecord,
    PortRecord,
    ScanHostRecord,
    ScanRecord,
    ServiceRecord,
)
from api.services import read
from read_factories import (
    make_finding,
    make_host,
    make_org,
    make_scan,
    make_scan_host,
)
from sqlmodel import Session


def _seed_mixed_severity_findings(session: Session) -> dict:
    org_a = make_org(session, "Mixed Severity A")
    org_b = make_org(session, "Mixed Severity B")
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    scan_a1 = make_scan(session, org_a.id, timestamp=base)
    scan_a2 = make_scan(
        session, org_a.id, timestamp=base - timedelta(hours=1)
    )
    scan_b1 = make_scan(session, org_b.id, timestamp=base)
    scan_b2 = make_scan(
        session, org_b.id, timestamp=base - timedelta(hours=1)
    )
    host_a1 = make_host(session, org_a.id, "192.168.10.1")
    host_a2 = make_host(session, org_a.id, "192.168.10.2")
    host_b1 = make_host(session, org_b.id, "192.168.20.1")
    host_b2 = make_host(session, org_b.id, "192.168.20.2")
    host_cross = make_host(session, org_b.id, "192.168.20.3")
    sh_a1 = make_scan_host(session, scan_a1.scan_id, host_a1.id, host_a1.ip)
    make_scan_host(session, scan_a2.scan_id, host_a2.id, host_a2.ip)
    sh_b1 = make_scan_host(session, scan_b1.scan_id, host_b1.id, host_b1.ip)
    make_scan_host(session, scan_b2.scan_id, host_b2.id, host_b2.ip)
    sh_cross_b1 = make_scan_host(
        session, scan_b1.scan_id, host_cross.id, host_cross.ip
    )
    sh_cross_b2 = make_scan_host(
        session, scan_b2.scan_id, host_cross.id, host_cross.ip
    )
    for i, severity in enumerate(["low", "medium", "high", "critical"]):
        make_finding(
            session,
            scan_a1.scan_id,
            sh_a1.id,
            f"org-a-all-{severity}",
            severity=severity,
        )
    for i, severity in enumerate(["low", "medium", "high", "critical"]):
        make_finding(
            session,
            scan_b1.scan_id,
            sh_b1.id,
            f"org-b-all-{severity}",
            severity=severity,
        )
    make_finding(
        session,
        scan_b1.scan_id,
        sh_cross_b1.id,
        "org-b-cross-b1-low",
        severity="low",
    )
    make_finding(
        session,
        scan_b2.scan_id,
        sh_cross_b2.id,
        "org-b-cross-b2-high",
        severity="high",
    )
    make_finding(
        session,
        scan_b2.scan_id,
        sh_cross_b2.id,
        "org-b-cross-b2-critical",
        severity="critical",
    )
    null_finding = make_finding(
        session,
        scan_b1.scan_id,
        None,
        "org-b-null-host",
        severity="high",
    )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "scan_a1": scan_a1,
        "scan_a2": scan_a2,
        "scan_b1": scan_b1,
        "scan_b2": scan_b2,
        "host_a1": host_a1,
        "host_b1": host_b1,
        "host_cross": host_cross,
        "null_finding": null_finding,
    }


def _seed_many_findings_for_paging(
    session: Session,
) -> tuple[Org, ScanRecord, ScanHostRecord]:
    org = make_org(session, "Finding Paging Org")
    scan = make_scan(session, org.id)
    host = make_host(session, org.id, "192.168.30.1")
    scan_host = make_scan_host(session, scan.scan_id, host.id, host.ip)
    for i in range(25):
        make_finding(
            session,
            scan.scan_id,
            scan_host.id,
            f"paging-medium-{i}",
            severity="medium",
        )
    return org, scan, scan_host


def _seed_tied_findings_for_stable_paging(
    session: Session,
) -> tuple[Org, list[FindingRecord]]:
    org = make_org(session, "Stable Finding Paging Org")
    scan = make_scan(session, org.id)
    host = make_host(session, org.id, "192.168.40.1")
    scan_host = make_scan_host(session, scan.scan_id, host.id, host.ip)
    tied_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    findings: list[FindingRecord] = []
    for i in range(25):
        findings.append(
            make_finding(
                session,
                scan.scan_id,
                scan_host.id,
                f"tied-low-{i}",
                severity="low",
                created_at=tied_at,
            )
        )
    return org, findings


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
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    make_host(administrative_session, org_a.id, "192.168.1.10")
    make_host(administrative_session, org_a.id, "192.168.1.11")
    make_host(administrative_session, org_b.id, "192.168.1.20")

    result_a = read.list_hosts(administrative_session, org_id=org_a.id)
    assert result_a.total == 2
    assert {str(row.ip) for row in result_a.data} == {"192.168.1.10", "192.168.1.11"}

    result_b = read.list_hosts(administrative_session, org_id=org_b.id)
    assert result_b.total == 1
    assert {str(row.ip) for row in result_b.data} == {"192.168.1.20"}


def test_get_host_detail_returns_none_for_foreign_org(
    administrative_session: Session,
) -> None:
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    host = make_host(administrative_session, org_a.id, "192.168.1.10")

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
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    host = make_host(administrative_session, org_a.id, "192.168.1.10")
    foreign_scan = make_scan(administrative_session, org_b.id)
    scan_host = make_scan_host(
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
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    host = make_host(administrative_session, org_a.id, "192.168.1.10")
    own_scan = make_scan(administrative_session, org_a.id)
    foreign_scan = make_scan(administrative_session, org_b.id)
    own_scan_host = make_scan_host(
        administrative_session, own_scan.scan_id, host.id, host.ip
    )
    foreign_scan_host = make_scan_host(
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
    administrative_session.add(
        HostPortRecord(
            host_id=host.id,
            port=443,
            protocol="tcp",
            service="https",
            first_seen_at=host.first_seen_at,
            last_seen_at=host.last_seen_at,
        )
    )
    administrative_session.commit()

    detail = read.get_host_detail(administrative_session, host.id, org_id=org_a.id)

    assert detail is not None
    assert {entry.scan_id for entry in detail.scan_history} == {own_scan.scan_id}
    assert {p.port for p in detail.ports} == {443}


def test_get_scan_detail_returns_none_for_foreign_org(
    administrative_session: Session,
) -> None:
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    scan = make_scan(administrative_session, org_a.id)

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
    org_a = make_org(administrative_session, "Org A")
    org_b = make_org(administrative_session, "Org B")
    host_a = make_host(administrative_session, org_a.id, "192.168.1.10")
    host_b = make_host(administrative_session, org_b.id, "192.168.1.20")
    scan_a = make_scan(administrative_session, org_a.id)
    scan_b = make_scan(administrative_session, org_b.id)
    scan_host_a = make_scan_host(
        administrative_session, scan_a.scan_id, host_a.id, host_a.ip
    )
    scan_host_b = make_scan_host(
        administrative_session, scan_b.scan_id, host_b.id, host_b.ip
    )
    finding_a = make_finding(
        administrative_session, scan_a.scan_id, scan_host_a.id, "dedupe-a"
    )
    make_finding(administrative_session, scan_b.scan_id, scan_host_b.id, "dedupe-b")

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
    org_a = make_org(administrative_session, "Org A")
    orphan_host = make_host(administrative_session, None, "192.168.1.30")
    orphan_scan = make_scan(administrative_session, None)

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



def test_list_findings_filters_by_severity(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=seeded["org_a"].id,
        severity="critical",
    )

    assert result.total == 1
    assert len(result.data) == 1
    assert all(row.severity == "critical" for row in result.data)


def test_list_findings_filters_by_scan_id(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=seeded["org_a"].id,
        scan_id=seeded["scan_a1"].scan_id,
    )

    assert result.total == 4
    assert all(row.scan_id == seeded["scan_a1"].scan_id for row in result.data)


def test_list_findings_severity_and_scan_combine(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)
    org_b = seeded["org_b"]
    scan_b1 = seeded["scan_b1"]

    by_severity = read.list_findings(
        administrative_session, org_id=org_b.id, severity="critical"
    )
    by_scan = read.list_findings(
        administrative_session, org_id=org_b.id, scan_id=scan_b1.scan_id
    )
    combined = read.list_findings(
        administrative_session,
        org_id=org_b.id,
        severity="critical",
        scan_id=scan_b1.scan_id,
    )

    assert combined.total == 1
    assert all(row.severity == "critical" for row in combined.data)
    assert all(row.scan_id == scan_b1.scan_id for row in combined.data)
    assert combined.total < by_severity.total
    assert combined.total < by_scan.total


def test_list_findings_host_and_scan_together(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=seeded["org_b"].id,
        host_id=seeded["host_cross"].id,
        scan_id=seeded["scan_b1"].scan_id,
    )

    assert result.total == 1
    assert result.data[0].severity == "low"
    assert result.data[0].scan_id == seeded["scan_b1"].scan_id
    assert result.data[0].host_id == seeded["host_cross"].id


def test_list_findings_no_severity_filter_returns_all_severities(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session, org_id=seeded["org_a"].id
    )

    assert result.total == 4
    assert {row.severity for row in result.data} == {
        "low",
        "medium",
        "high",
        "critical",
    }


def test_list_findings_paging_total_counts_matches(
    administrative_session: Session,
) -> None:
    org, _, _ = _seed_many_findings_for_paging(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=org.id,
        severity="medium",
        page=1,
        per_page=20,
    )

    assert len(result.data) == 20
    assert result.total == 25


def test_list_findings_empty_filter_result(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=seeded["org_a"].id,
        scan_id=seeded["scan_a2"].scan_id,
        severity="critical",
    )

    assert result.total == 0
    assert result.data == []


def test_list_findings_org_isolation(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)
    org_a = seeded["org_a"]
    org_b = seeded["org_b"]
    org_b_all = read.list_findings(
        administrative_session, org_id=org_b.id, per_page=100
    )
    org_b_finding_ids = {row.finding_id for row in org_b_all.data}

    by_foreign_scan = read.list_findings(
        administrative_session,
        org_id=org_a.id,
        scan_id=seeded["scan_b1"].scan_id,
    )
    by_foreign_host = read.list_findings(
        administrative_session,
        org_id=org_a.id,
        host_id=seeded["host_b1"].id,
    )
    by_foreign_both = read.list_findings(
        administrative_session,
        org_id=org_a.id,
        scan_id=seeded["scan_b1"].scan_id,
        host_id=seeded["host_b1"].id,
    )

    for result in (by_foreign_scan, by_foreign_host, by_foreign_both):
        assert result.total == 0
        assert result.data == []
        assert org_b_finding_ids.isdisjoint({row.finding_id for row in result.data})


def test_list_findings_null_scan_host_included_unfiltered(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session, org_id=seeded["org_b"].id
    )

    null_rows = [
        row
        for row in result.data
        if row.finding_id == seeded["null_finding"].finding_id
    ]
    assert len(null_rows) == 1
    assert null_rows[0].host_id is None


def test_list_findings_zero_finding_scan_returns_empty(
    administrative_session: Session,
) -> None:
    seeded = _seed_mixed_severity_findings(administrative_session)

    result = read.list_findings(
        administrative_session,
        org_id=seeded["org_a"].id,
        scan_id=seeded["scan_a2"].scan_id,
    )

    assert result.total == 0
    assert result.data == []


def test_list_findings_stable_paging_under_ties(
    administrative_session: Session,
) -> None:
    org, findings = _seed_tied_findings_for_stable_paging(administrative_session)
    expected_ids = {finding.finding_id for finding in findings}

    seen: set = set()
    for page in range(1, 4):
        result = read.list_findings(
            administrative_session,
            org_id=org.id,
            severity="low",
            page=page,
            per_page=10,
        )
        page_ids = {row.finding_id for row in result.data}
        assert seen.isdisjoint(page_ids)
        seen |= page_ids
        assert result.total == 25

    assert seen == expected_ids
