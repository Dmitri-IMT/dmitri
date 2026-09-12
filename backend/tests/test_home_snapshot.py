from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from api.core.home_constants import (
    HOME_ACTIVITY_PER_PAGE,
    HOME_ATTENTION_PER_PAGE,
    STALE_COVERAGE_DAYS,
)
from api.models.identity import Org
from api.models.persistence import HostRecord, ScanHostRecord, ScanRecord
from api.services.activity import ActivityAppend, append_activity
from api.services.home import read_home_snapshot
from read_factories import make_finding, make_host, make_org, make_scan, make_scan_host
from sqlmodel import Session, select

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    session: Session,
    org_id: UUID,
    *,
    role: str = "admin",
    attention_page: int = 1,
    activity_page: int = 1,
    now: datetime = NOW,
):
    return read_home_snapshot(
        session,
        org_id=org_id,
        role=role,
        attention_page=attention_page,
        events_page=1,
        activity_page=activity_page,
        now=now,
    )


def _scan_host_for(session: Session, org_id: UUID, scan: ScanRecord, ip: str):
    host = make_host(session, org_id, ip)
    host.first_seen_at = scan.timestamp
    host.last_seen_at = scan.timestamp
    session.add(host)
    session.commit()
    session.refresh(host)
    return make_scan_host(session, scan.scan_id, host.id, ip)


def _seed_attention(
    session: Session,
    *,
    name: str,
    severities: list[str],
    created_at: datetime | None = None,
    status: str = "completed",
) -> tuple[Org, ScanRecord]:
    org = make_org(session, name)
    scan = make_scan(session, org.id, timestamp=NOW, status=status)
    scan_host = _scan_host_for(session, org.id, scan, "192.168.1.10")
    for i, severity in enumerate(severities):
        make_finding(
            session,
            scan.scan_id,
            scan_host.id,
            f"{name}-{i}",
            severity=severity,
            created_at=created_at,
        )
    return org, scan


def _append(
    session: Session, org_id: UUID, hostname: str, occurred_at: datetime
) -> None:
    append_activity(
        session,
        ActivityAppend(
            org_id=org_id,
            kind="machine_first_seen",
            occurred_at=occurred_at,
            actor_user_id=None,
            subject_id=uuid4(),
            payload={"hostname": hostname},
        ),
    )
    session.commit()


def test_attention_orders_critical_before_high_newest_first_across_pages(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Attention Order")
    scan = make_scan(administrative_session, org.id, timestamp=NOW)
    scan_host = _scan_host_for(administrative_session, org.id, scan, "192.168.1.11")
    for i in range(6):
        make_finding(
            administrative_session,
            scan.scan_id,
            scan_host.id,
            f"critical-{i}",
            severity="critical",
            created_at=NOW - timedelta(minutes=i),
        )
    for i in range(6):
        make_finding(
            administrative_session,
            scan.scan_id,
            scan_host.id,
            f"high-{i}",
            severity="high",
            created_at=NOW - timedelta(minutes=i),
        )

    page_one = _snapshot(administrative_session, org.id, attention_page=1).attention
    page_two = _snapshot(administrative_session, org.id, attention_page=2).attention
    rows = page_one.data + page_two.data

    assert [row.severity for row in rows] == ["critical"] * 6 + ["high"] * 6
    criticals = [row.detected_at for row in rows[:6]]
    highs = [row.detected_at for row in rows[6:]]
    assert criticals == sorted(criticals, reverse=True)
    assert highs == sorted(highs, reverse=True)


def test_attention_tied_created_at_pages_without_repeat_or_gap(
    administrative_session: Session,
) -> None:
    total = HOME_ATTENTION_PER_PAGE + 4
    org, _ = _seed_attention(
        administrative_session,
        name="Attention Ties",
        severities=["high"] * total,
        created_at=NOW,
    )

    page_one = _snapshot(administrative_session, org.id, attention_page=1).attention
    page_two = _snapshot(administrative_session, org.id, attention_page=2).attention
    ids = [row.finding_id for row in page_one.data + page_two.data]

    assert len(page_one.data) == HOME_ATTENTION_PER_PAGE
    assert len(ids) == total
    assert len(set(ids)) == total
    assert page_one.total == total


def test_medium_and_low_never_reach_attention(
    administrative_session: Session,
) -> None:
    org, _ = _seed_attention(
        administrative_session,
        name="Attention Severity Filter",
        severities=["critical", "high", "medium", "low"],
    )

    attention = _snapshot(administrative_session, org.id).attention

    assert attention.total == 2
    assert {row.severity for row in attention.data} == {"critical", "high"}


def test_review_count_uses_totals_not_current_page(
    administrative_session: Session,
) -> None:
    total = HOME_ATTENTION_PER_PAGE + 2
    org, _ = _seed_attention(
        administrative_session,
        name="Review Count",
        severities=["critical"] * total,
        status="failed",
    )

    snapshot = _snapshot(administrative_session, org.id, attention_page=2)

    assert len(snapshot.attention.data) == 2
    assert snapshot.attention.total == total
    assert snapshot.review_count == total + len(snapshot.notices)
    assert snapshot.review_count != len(snapshot.attention.data)


def test_review_state_blank_without_any_scan(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Blank Org")

    snapshot = _snapshot(administrative_session, org.id)

    assert snapshot.review_state == "blank"
    assert snapshot.review_count == 0
    assert snapshot.attention.data == []


def test_review_state_clear_and_pending(
    administrative_session: Session,
) -> None:
    clear_org, _ = _seed_attention(
        administrative_session, name="Clear Org", severities=[]
    )
    pending_org, _ = _seed_attention(
        administrative_session, name="Pending Org", severities=["high"]
    )

    clear = _snapshot(administrative_session, clear_org.id)
    pending = _snapshot(administrative_session, pending_org.id)

    assert (clear.review_state, clear.review_count) == ("clear", 0)
    assert pending.review_state == "pending"
    assert pending.review_count == 1


def test_attention_page_past_the_end_is_empty_with_real_total(
    administrative_session: Session,
) -> None:
    org, _ = _seed_attention(
        administrative_session, name="Past End", severities=["high", "critical"]
    )

    attention = _snapshot(administrative_session, org.id, attention_page=9).attention

    assert attention.data == []
    assert attention.total == 2
    assert attention.page == 9


def test_stale_coverage_boundary_excludes_exact_threshold(
    administrative_session: Session,
) -> None:
    fresh = make_org(administrative_session, "Fresh Coverage")
    make_scan(
        administrative_session,
        fresh.id,
        timestamp=NOW - timedelta(days=STALE_COVERAGE_DAYS),
    )
    stale = make_org(administrative_session, "Stale Coverage")
    make_scan(
        administrative_session,
        stale.id,
        timestamp=NOW - timedelta(days=STALE_COVERAGE_DAYS + 1),
    )

    fresh_notices = _snapshot(administrative_session, fresh.id).notices
    stale_notices = _snapshot(administrative_session, stale.id).notices

    assert [n.kind for n in fresh_notices] == []
    assert [n.kind for n in stale_notices] == ["stale_coverage"]
    assert stale_notices[0].days == STALE_COVERAGE_DAYS + 1


def test_failed_latest_scan_notices_and_stays_out_of_events(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Failed Scan Org")
    make_scan(administrative_session, org.id, timestamp=NOW, status="failed")

    snapshot = _snapshot(administrative_session, org.id)

    assert [n.kind for n in snapshot.notices] == ["failed_scan"]
    assert snapshot.review_state == "pending"
    assert snapshot.review_count == 1
    assert snapshot.events.data == []


def test_events_is_an_empty_page(administrative_session: Session) -> None:
    org, _ = _seed_attention(
        administrative_session, name="Events Empty", severities=["high"]
    )

    events = _snapshot(administrative_session, org.id).events

    assert events.data == []
    assert events.total == 0
    assert events.page == 1


def test_activity_ties_page_newest_written_first(
    administrative_session: Session,
) -> None:
    total = HOME_ACTIVITY_PER_PAGE + 3
    org = make_org(administrative_session, "Activity Ties")
    for i in range(total):
        _append(administrative_session, org.id, f"machine-{i}", NOW)

    page_one = _snapshot(administrative_session, org.id, activity_page=1).activity
    page_two = _snapshot(administrative_session, org.id, activity_page=2).activity
    texts = [item.text for item in page_one.data + page_two.data]

    assert page_one.total == total
    assert len(page_one.data) == HOME_ACTIVITY_PER_PAGE
    assert len(texts) == total
    assert len(set(texts)) == total
    assert texts[0] == f"machine-{total - 1} first seen on the network"


def test_activity_is_newest_first_across_times(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Activity Order")
    _append(administrative_session, org.id, "older", NOW - timedelta(hours=2))
    _append(administrative_session, org.id, "newer", NOW - timedelta(hours=1))

    activity = _snapshot(administrative_session, org.id).activity

    assert [item.occurred_at for item in activity.data] == sorted(
        [item.occurred_at for item in activity.data], reverse=True
    )
    assert activity.data[0].text.startswith("newer")


def test_attention_rows_carry_the_machines_current_name(
    administrative_session: Session,
) -> None:
    org, _ = _seed_attention(
        administrative_session,
        name="Attention Machine Name",
        severities=["critical"],
    )
    host = administrative_session.exec(
        select(HostRecord).where(HostRecord.org_id == org.id)
    ).one()
    host.hostname = "renamed-machine"
    scan_host = administrative_session.exec(
        select(ScanHostRecord).where(ScanHostRecord.host_id == host.id)
    ).one()
    scan_host.hostname = "name-at-scan-time"
    administrative_session.add(host)
    administrative_session.add(scan_host)
    administrative_session.commit()

    attention = _snapshot(administrative_session, org.id).attention

    assert [row.host_hostname for row in attention.data] == ["renamed-machine"]
    assert [row.host_id for row in attention.data] == [host.id]
