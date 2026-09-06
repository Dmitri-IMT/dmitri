from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from api.core.home_constants import (
    BOX_OFFLINE_DAYS,
    HOME_EVENTS_PER_PAGE,
    MEMBER_IDLE_DAYS,
    STALE_COVERAGE_DAYS,
)
from api.models.command import Agent
from api.models.identity import User
from api.models.persistence import HostRecord
from api.services import agent_connections
from api.services.home import derive_home_events, read_home_snapshot
from api.services.passwords import hash_password
from read_factories import make_org, make_scan
from sqlmodel import Session

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
VALID_PASSWORD = "correct-horse-battery-staple"  # pragma: allowlist secret


def _derive(session: Session, org_id, *, now: datetime = NOW):
    return derive_home_events(session, org_id=org_id, now=now)


def _snapshot(
    session: Session,
    org_id,
    *,
    role: str = "admin",
    events_page: int = 1,
    now: datetime = NOW,
):
    return read_home_snapshot(
        session,
        org_id=org_id,
        role=role,
        attention_page=1,
        events_page=events_page,
        activity_page=1,
        now=now,
    )


def _agent(
    session: Session,
    org_id,
    *,
    display_name: str = "Office Box",
    last_seen_at: datetime | None = None,
) -> Agent:
    agent = Agent(
        org_id=org_id,
        display_name=display_name,
        public_key=b"\x01" * 32,
        last_seen_at=last_seen_at,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _user(
    session: Session,
    org_id,
    *,
    email: str,
    role: str = "viewer",
    last_login_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    created_at: datetime | None = None,
) -> User:
    user = User(
        org_id=org_id,
        email=email,
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
        last_login_at=last_login_at,
        last_seen_at=last_seen_at,
    )
    if created_at is not None:
        user.created_at = created_at
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _host(
    session: Session,
    org_id,
    *,
    hostname: str,
    first_seen_at: datetime,
    ip: str | None = None,
) -> HostRecord:
    resolved_ip = ip or f"192.168.1.{hash(hostname) % 200 + 10}"
    host = HostRecord(
        org_id=org_id,
        identity_key=f"identity-{hostname}",
        ip=resolved_ip,
        mac=f"aa:bb:cc:dd:ee:{len(hostname):02x}",
        hostname=hostname,
        vendor="vendor",
        open_ports_count=0,
        highest_severity=None,
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
    )
    session.add(host)
    session.commit()
    session.refresh(host)
    return host


def test_box_offline_after_threshold_with_correct_day_count(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Offline Box")
    last_seen = NOW - timedelta(days=BOX_OFFLINE_DAYS + 1)
    _agent(administrative_session, org.id, last_seen_at=last_seen)

    events = _derive(administrative_session, org.id)

    assert len(events) == 1
    assert events[0].kind.value == "box_offline"
    assert events[0].text == (
        f"Office Box has been offline for {BOX_OFFLINE_DAYS + 1} days"
    )
    assert events[0].occurred_at == last_seen


def test_live_box_with_stale_db_last_seen_yields_no_offline_event(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Live Box")
    agent = _agent(
        administrative_session,
        org.id,
        last_seen_at=NOW - timedelta(days=BOX_OFFLINE_DAYS + 1),
    )
    ws = AsyncMock()

    async def run() -> None:
        await agent_connections.register(agent.id, ws, now=NOW)

    asyncio.run(run())

    events = _derive(administrative_session, org.id)

    assert events == []


def test_member_idle_when_last_login_is_stale(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Idle Member")
    stale_login = NOW - timedelta(days=MEMBER_IDLE_DAYS + 1)
    _user(
        administrative_session,
        org.id,
        email="idle@corp.com",
        last_login_at=stale_login,
    )

    events = _derive(administrative_session, org.id)

    assert len(events) == 1
    assert events[0].kind.value == "member_idle"
    assert events[0].text == (
        f"idle@corp.com has not signed in for {MEMBER_IDLE_DAYS + 1} days"
    )
    assert events[0].occurred_at == stale_login


def test_member_idle_when_last_login_is_null_uses_created_at(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Never Logged In")
    created_at = NOW - timedelta(days=MEMBER_IDLE_DAYS + 2)
    _user(
        administrative_session,
        org.id,
        email="never@corp.com",
        created_at=created_at,
    )

    events = _derive(administrative_session, org.id)

    assert len(events) == 1
    assert events[0].text == (
        f"never@corp.com has not signed in for {MEMBER_IDLE_DAYS + 2} days"
    )
    assert events[0].occurred_at == created_at


def test_fresh_last_seen_with_stale_last_login_is_still_idle(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Session Refresh")
    stale_login = NOW - timedelta(days=MEMBER_IDLE_DAYS + 1)
    _user(
        administrative_session,
        org.id,
        email="refresh@corp.com",
        last_login_at=stale_login,
        last_seen_at=NOW,
    )

    events = _derive(administrative_session, org.id)

    assert len(events) == 1
    assert events[0].kind.value == "member_idle"


def test_viewer_snapshot_carries_same_idle_events_as_admin(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Viewer Parity")
    stale_login = NOW - timedelta(days=MEMBER_IDLE_DAYS + 1)
    _user(
        administrative_session,
        org.id,
        email="viewer@corp.com",
        last_login_at=stale_login,
    )

    admin_events = _snapshot(administrative_session, org.id, role="admin").events
    viewer_events = _snapshot(administrative_session, org.id, role="viewer").events

    assert admin_events.data == viewer_events.data
    assert admin_events.total == viewer_events.total == 1


def test_new_machine_on_later_scan_yields_event_baseline_hosts_do_not(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Machine Events")
    baseline_time = NOW - timedelta(days=10)
    make_scan(administrative_session, org.id, timestamp=baseline_time)
    _host(
        administrative_session,
        org.id,
        hostname="baseline-host",
        first_seen_at=baseline_time,
    )
    later_scan_time = NOW - timedelta(days=1)
    make_scan(administrative_session, org.id, timestamp=later_scan_time)
    _host(
        administrative_session,
        org.id,
        hostname="new-laptop",
        first_seen_at=later_scan_time,
        ip="192.168.1.50",
    )

    events = _derive(administrative_session, org.id)

    assert len(events) == 1
    assert events[0].kind.value == "machine_first_seen"
    assert events[0].text == "New machine joined the network: new-laptop"
    assert events[0].occurred_at == later_scan_time
    assert "device" not in events[0].text.lower()


def test_event_copy_uses_box_and_machine_vocabulary(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Vocabulary")
    _agent(
        administrative_session,
        org.id,
        display_name="Kitchen Box",
        last_seen_at=NOW - timedelta(days=BOX_OFFLINE_DAYS + 1),
    )
    baseline_time = NOW - timedelta(days=5)
    make_scan(administrative_session, org.id, timestamp=baseline_time)
    _host(
        administrative_session,
        org.id,
        hostname="printer",
        first_seen_at=NOW - timedelta(days=1),
        ip="192.168.1.60",
    )

    texts = [event.text for event in _derive(administrative_session, org.id)]

    assert any("Box" in text for text in texts)
    assert any("machine joined the network" in text for text in texts)
    assert all("device joined the network" not in text for text in texts)


def test_stale_coverage_stays_a_notice_not_an_event(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Stale Coverage")
    make_scan(
        administrative_session,
        org.id,
        timestamp=NOW - timedelta(days=STALE_COVERAGE_DAYS + 1),
    )

    snapshot = _snapshot(administrative_session, org.id)

    assert [notice.kind for notice in snapshot.notices] == ["stale_coverage"]
    assert snapshot.events.data == []
    assert snapshot.events.total == 0


def test_events_paginate_independently_and_empty_page_keeps_total(
    administrative_session: Session,
) -> None:
    org = make_org(administrative_session, "Events Pagination")
    for offset in range(HOME_EVENTS_PER_PAGE + 2):
        _user(
            administrative_session,
            org.id,
            email=f"idle-{offset}@corp.com",
            last_login_at=NOW - timedelta(days=MEMBER_IDLE_DAYS + offset + 1),
        )

    page_one = _snapshot(administrative_session, org.id, events_page=1).events
    page_two = _snapshot(administrative_session, org.id, events_page=2).events
    page_past_end = _snapshot(
        administrative_session, org.id, events_page=9
    ).events

    total = HOME_EVENTS_PER_PAGE + 2
    assert page_one.total == total
    assert len(page_one.data) == HOME_EVENTS_PER_PAGE
    assert len(page_two.data) == 2
    assert page_past_end.data == []
    assert page_past_end.total == total
    assert page_past_end.page == 9
