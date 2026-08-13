from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product
from uuid import uuid4

import pytest
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.services import read
from read_factories import make_finding, make_host, make_org, make_scan, make_scan_host
from sqlalchemy import event
from sqlmodel import Session


def _seed_command(
    session: Session,
    org_id,
    scan_id,
    *,
    status: str,
    error_code: str | None = None,
) -> Command:
    agent = Agent(
        org_id=org_id,
        display_name=f"agent-{uuid4()}",
        public_key=b"\x01" * 32,
    )
    session.add(agent)
    session.flush()
    command = Command(
        org_id=org_id,
        agent_id=agent.id,
        scan_id=scan_id,
        scan_mode="quick",
        subnet="192.168.1.0/24",
        status=status,
        error_code=error_code,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _seed_scan_history_org(
    session: Session,
) -> tuple[Org, Org, list[ScanRecord], list[ScanRecord]]:
    org_a = make_org(session, "Scan History A")
    org_b = make_org(session, "Scan History B")
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    scans_a: list[ScanRecord] = []
    for i in range(25):
        scan = ScanRecord(
            scan_id=uuid4(),
            org_id=org_a.id,
            timestamp=base + timedelta(hours=i),
            subnet=f"10.0.{i // 256}.{i % 256}/24",
            scan_mode="quick" if i % 2 == 0 else "standard",
            status="failed" if i % 3 == 0 else "completed",
            metadata_json={},
        )
        session.add(scan)
        scans_a.append(scan)
    session.commit()
    for scan in scans_a:
        session.refresh(scan)
    scans_b = [
        make_scan(
            session,
            org_b.id,
            timestamp=base + timedelta(days=1, hours=i),
            status="completed" if i % 2 == 0 else "failed",
            scan_mode="standard",
            subnet=f"10.1.0.{i}/24",
        )
        for i in range(5)
    ]
    return org_a, org_b, scans_a, scans_b


def _seed_aggregate_scans(
    session: Session,
) -> tuple[Org, ScanRecord, ScanRecord, ScanRecord]:
    org = make_org(session, "Aggregate Org")
    base = datetime(2026, 2, 1, tzinfo=timezone.utc)
    scan_a = make_scan(
        session, org.id, timestamp=base, status="completed", scan_mode="standard"
    )
    scan_b = make_scan(
        session,
        org.id,
        timestamp=base - timedelta(days=1),
        status="completed",
        scan_mode="quick",
    )
    scan_empty = make_scan(
        session,
        org.id,
        timestamp=base - timedelta(days=2),
        status="completed",
        scan_mode="quick",
    )
    hosts_a = [
        make_host(session, org.id, f"192.168.1.{i}") for i in range(10, 22)
    ]
    scan_hosts_a = []
    for host in hosts_a:
        scan_hosts_a.append(
            make_scan_host(session, scan_a.scan_id, host.id, host.ip)
        )
    scan_hosts_b = []
    for i in range(3):
        host = make_host(session, org.id, f"192.168.2.{i}")
        scan_hosts_b.append(
            make_scan_host(session, scan_b.scan_id, host.id, host.ip)
        )
    severities_a = ["low", "medium", "high", "critical"]
    for i, severity in enumerate(severities_a):
        make_finding(
            session,
            scan_a.scan_id,
            scan_hosts_a[i].id,
            f"dedupe-a-{i}",
            severity=severity,
        )
    for i, sh in enumerate(scan_hosts_b[:2]):
        make_finding(
            session,
            scan_b.scan_id,
            sh.id,
            f"dedupe-b-{i}",
            severity="medium" if i == 0 else "low",
        )
    return org, scan_a, scan_b, scan_empty


def test_list_scans_per_page_one_returns_latest(
    administrative_session: Session,
) -> None:
    org_a, _, scans_a, _ = _seed_scan_history_org(administrative_session)
    newest = max(scans_a, key=lambda s: s.timestamp)

    result = read.list_scans(administrative_session, org_id=org_a.id, per_page=1)

    assert len(result.data) == 1
    assert result.data[0].scan_id == newest.scan_id


def test_list_scans_default_order_newest_first(
    administrative_session: Session,
) -> None:
    org_a, _, _, _ = _seed_scan_history_org(administrative_session)

    result = read.list_scans(administrative_session, org_id=org_a.id)

    timestamps = [row.timestamp for row in result.data]
    assert timestamps == sorted(timestamps, reverse=True)


def test_list_scans_sort_order_asc_returns_oldest_first(
    administrative_session: Session,
) -> None:
    org_a, _, scans_a, _ = _seed_scan_history_org(administrative_session)
    oldest = min(scans_a, key=lambda s: s.timestamp)

    result = read.list_scans(
        administrative_session, org_id=org_a.id, sort_order="asc"
    )

    assert result.data[0].scan_id == oldest.scan_id


@pytest.mark.parametrize("sort_by", ["status", "scan_mode"])
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_list_scans_sort_column_is_monotonic(
    administrative_session: Session,
    sort_by: str,
    sort_order: str,
) -> None:
    org_a, _, _, _ = _seed_scan_history_org(administrative_session)

    result = read.list_scans(
        administrative_session,
        org_id=org_a.id,
        sort_by=sort_by,
        sort_order=sort_order,
        per_page=100,
    )

    values = [getattr(row, sort_by) for row in result.data]
    expected = sorted(values, reverse=sort_order == "desc")
    assert values == expected


def test_list_scans_empty_org(administrative_session: Session) -> None:
    org = make_org(administrative_session, "Empty Org")

    result = read.list_scans(administrative_session, org_id=org.id)

    assert result.total == 0
    assert result.data == []


def test_list_scans_paging(administrative_session: Session) -> None:
    org_a, _, _, _ = _seed_scan_history_org(administrative_session)

    page1 = read.list_scans(
        administrative_session, org_id=org_a.id, page=1, per_page=20
    )
    page2 = read.list_scans(
        administrative_session, org_id=org_a.id, page=2, per_page=20
    )

    page1_ids = {row.scan_id for row in page1.data}
    page2_ids = {row.scan_id for row in page2.data}
    assert len(page1.data) == 20
    assert len(page2.data) == 5
    assert page1.total == 25
    assert page2.total == 25
    assert page1_ids & page2_ids == set()
    assert len(page1_ids | page2_ids) == 25


def test_list_scans_page_past_end(administrative_session: Session) -> None:
    org = make_org(administrative_session, "Small Org")
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for i in range(3):
        make_scan(
            administrative_session,
            org.id,
            timestamp=base + timedelta(hours=i),
        )

    result = read.list_scans(
        administrative_session, org_id=org.id, page=5, per_page=20
    )

    assert result.data == []
    assert result.total == 3


def test_list_scans_filters_by_status(administrative_session: Session) -> None:
    org_a, _, scans_a, _ = _seed_scan_history_org(administrative_session)
    failed_ids = {s.scan_id for s in scans_a if s.status == "failed"}

    result = read.list_scans(
        administrative_session, org_id=org_a.id, status="failed", per_page=100
    )

    assert result.total == len(failed_ids)
    assert len(result.data) == len(failed_ids)
    assert {row.scan_id for row in result.data} == failed_ids
    assert all(row.status == "failed" for row in result.data)


def test_list_scans_per_scan_aggregates(
    administrative_session: Session,
) -> None:
    org, scan_a, scan_b, _ = _seed_aggregate_scans(administrative_session)

    result = read.list_scans(
        administrative_session, org_id=org.id, per_page=100, sort_order="asc"
    )
    by_id = {row.scan_id: row for row in result.data}

    assert by_id[scan_a.scan_id].host_count == 12
    assert by_id[scan_a.scan_id].finding_count == 4
    assert by_id[scan_a.scan_id].highest_severity == "critical"
    assert by_id[scan_b.scan_id].host_count == 3
    assert by_id[scan_b.scan_id].finding_count == 2
    assert by_id[scan_b.scan_id].highest_severity == "medium"


def test_list_scans_zero_findings_has_null_highest_severity(
    administrative_session: Session,
) -> None:
    org, _, _, scan_empty = _seed_aggregate_scans(administrative_session)

    result = read.list_scans(
        administrative_session, org_id=org.id, per_page=100, sort_order="asc"
    )
    row = next(r for r in result.data if r.scan_id == scan_empty.scan_id)

    assert row.finding_count == 0
    assert row.highest_severity is None


def test_list_scans_severity_ranking_not_lexical(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Severity Rank Org")
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    scan_lc = make_scan(
        administrative_session, org.id, timestamp=base, scan_mode="quick"
    )
    scan_lm = make_scan(
        administrative_session,
        org.id,
        timestamp=base - timedelta(hours=1),
        scan_mode="standard",
    )
    host_lc = make_host(administrative_session, org.id, "192.168.3.1")
    host_lm = make_host(administrative_session, org.id, "192.168.3.2")
    sh_lc = make_scan_host(
        administrative_session, scan_lc.scan_id, host_lc.id, host_lc.ip
    )
    sh_lm = make_scan_host(
        administrative_session, scan_lm.scan_id, host_lm.id, host_lm.ip
    )
    make_finding(
        administrative_session, scan_lc.scan_id, sh_lc.id, "lc-low", severity="low"
    )
    make_finding(
        administrative_session,
        scan_lc.scan_id,
        sh_lc.id,
        "lc-critical",
        severity="critical",
    )
    make_finding(
        administrative_session, scan_lm.scan_id, sh_lm.id, "lm-low", severity="low"
    )
    make_finding(
        administrative_session,
        scan_lm.scan_id,
        sh_lm.id,
        "lm-medium",
        severity="medium",
    )

    result = read.list_scans(administrative_session, org_id=org.id, per_page=100)
    by_id = {row.scan_id: row for row in result.data}

    assert by_id[scan_lc.scan_id].highest_severity == "critical"
    assert by_id[scan_lm.scan_id].highest_severity == "medium"


def test_list_scans_org_isolation(
    administrative_session: Session,
) -> None:
    org_a, org_b, scans_a, scans_b = _seed_scan_history_org(administrative_session)
    org_a_ids = {s.scan_id for s in scans_a}
    org_b_ids = {s.scan_id for s in scans_b}

    for status, sort_by, sort_order, page in product(
        [None, "completed", "failed"],
        ["timestamp", "status", "scan_mode"],
        ["asc", "desc"],
        [1, 2, 3],
    ):
        kwargs: dict = {
            "org_id": org_a.id,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "per_page": 10,
        }
        if status is not None:
            kwargs["status"] = status
        result = read.list_scans(administrative_session, **kwargs)
        returned = {row.scan_id for row in result.data}
        assert returned <= org_a_ids
        assert returned.isdisjoint(org_b_ids)


def test_null_org_id_scan_invisible_in_list_scans(
    administrative_session: Session,
) -> None:
    org_a = make_org(administrative_session, "Org A")
    orphan_scan = make_scan(administrative_session, None)

    result = read.list_scans(administrative_session, org_id=org_a.id)

    assert orphan_scan.scan_id not in {row.scan_id for row in result.data}


def test_list_scans_stable_paging_under_status_ties(
    administrative_session: Session,
) -> None:
    org_a, _, _, _ = _seed_scan_history_org(administrative_session)

    seen: set = set()
    for page in range(1, 6):
        result = read.list_scans(
            administrative_session,
            org_id=org_a.id,
            sort_by="status",
            sort_order="asc",
            page=page,
            per_page=5,
        )
        page_ids = {row.scan_id for row in result.data}
        assert seen.isdisjoint(page_ids)
        seen |= page_ids
        assert result.total == 25

    assert len(seen) == 25


def test_list_scans_query_count_constant_in_per_page(
    administrative_session: Session,
) -> None:
    org_a, _, _, _ = _seed_scan_history_org(administrative_session)
    read.list_scans(administrative_session, org_id=org_a.id, per_page=1)
    counts: list[int] = []
    engine = administrative_session.get_bind()

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        counts.append(1)

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        read.list_scans(administrative_session, org_id=org_a.id, per_page=20)
        after_large = len(counts)
        read.list_scans(
            administrative_session, org_id=org_a.id, per_page=5, page=2
        )
        after_small = len(counts)
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)

    assert after_large == after_small - after_large
    assert after_large <= 4


def test_get_scan_detail_failed_published_code_from_one_request(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Failed Published Org")
    scan = make_scan(administrative_session, org.id, status="failed")
    command = _seed_command(
        administrative_session,
        org.id,
        scan.scan_id,
        status="failed",
        error_code="scan_failed",
    )

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=org.id
    )

    assert detail is not None
    assert detail.error_code == "scan_failed"
    assert detail.command_id == command.id


def test_get_scan_detail_failed_null_code_is_unknown(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Failed Null Code Org")
    scan = make_scan(administrative_session, org.id, status="failed")
    _seed_command(
        administrative_session, org.id, scan.scan_id, status="failed"
    )

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=org.id
    )

    assert detail is not None
    assert detail.error_code == "unknown"


def test_get_scan_detail_failed_off_contract_code_is_unknown(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Failed Off Contract Org")
    scan = make_scan(administrative_session, org.id, status="failed")
    _seed_command(
        administrative_session,
        org.id,
        scan.scan_id,
        status="failed",
        error_code="scan_timeout",
    )

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=org.id
    )

    assert detail is not None
    assert detail.error_code == "unknown"


def test_get_scan_detail_failed_without_command_is_unknown(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Failed No Command Org")
    scan = make_scan(administrative_session, org.id, status="failed")

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=org.id
    )

    assert detail is not None
    assert detail.error_code == "unknown"
    assert detail.command_id is None


def test_get_scan_detail_completed_hides_stored_error_code(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Completed Stored Code Org")
    scan = make_scan(administrative_session, org.id, status="completed")
    command = _seed_command(
        administrative_session,
        org.id,
        scan.scan_id,
        status="done",
        error_code="scan_failed",
    )

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=org.id
    )

    assert detail is not None
    assert detail.error_code is None
    assert detail.command_id == command.id


def test_list_scans_row_omits_error_code(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "List Omits Error Code Org")
    scan = make_scan(administrative_session, org.id, status="failed")
    _seed_command(
        administrative_session,
        org.id,
        scan.scan_id,
        status="failed",
        error_code="scan_failed",
    )

    result = read.list_scans(administrative_session, org_id=org.id)

    assert len(result.data) == 1
    assert "error_code" not in result.data[0].model_dump()
