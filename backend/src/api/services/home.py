from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, or_
from sqlmodel import Session, func, select

from api.core.home_constants import (
    BOX_OFFLINE_DAYS,
    HOME_ACTIVITY_PER_PAGE,
    HOME_ATTENTION_PER_PAGE,
    HOME_EVENTS_PER_PAGE,
    MACHINE_FIRST_SEEN_RECENT_DAYS,
    MEMBER_IDLE_DAYS,
    STALE_COVERAGE_DAYS,
)
from api.models.activity import ActivityRecord
from api.models.command import Agent
from api.models.identity import User
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    ScanRecord,
)
from api.schemas.home import (
    HomeActivityItem,
    HomeActivityPage,
    HomeAttentionPage,
    HomeEvent,
    HomeEventKind,
    HomeEventsPage,
    HomeNotice,
    HomeSnapshot,
)
from api.schemas.read import ScanSummary
from api.services import agent_connections, read
from api.services.activity import activity_text

ATTENTION_SEVERITIES = ("critical", "high")

_ATTENTION_RANK = case(
    {"critical": 0}, value=FindingRecord.severity, else_=1
)


def page_attention(
    session: Session, *, org_id: UUID, scan_id: UUID | None, page: int
) -> HomeAttentionPage:
    if scan_id is None:
        return HomeAttentionPage(data=[], total=0, page=page)

    base = (
        read.finding_read_query()
        .join(ScanRecord, FindingRecord.scan_id == ScanRecord.scan_id)
        .where(ScanRecord.org_id == org_id)
        .where(FindingRecord.scan_id == scan_id)
        .where(FindingRecord.severity.in_(ATTENTION_SEVERITIES))
    )
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(
        base.order_by(
            _ATTENTION_RANK,
            FindingRecord.created_at.desc(),
            FindingRecord.id.desc(),
        )
        .offset((page - 1) * HOME_ATTENTION_PER_PAGE)
        .limit(HOME_ATTENTION_PER_PAGE)
    ).all()

    return HomeAttentionPage(
        data=read.to_finding_reads(rows),
        total=total,
        page=page,
    )


def list_org_activity(
    session: Session, *, org_id: UUID, role: str, page: int, per_page: int
) -> tuple[list[HomeActivityItem], int]:
    total = session.exec(
        select(func.count())
        .select_from(ActivityRecord)
        .where(ActivityRecord.org_id == org_id)
    ).one()
    rows = session.exec(
        select(ActivityRecord)
        .where(ActivityRecord.org_id == org_id)
        .order_by(ActivityRecord.occurred_at.desc(), ActivityRecord.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    items = [
        HomeActivityItem(
            kind=row.kind,
            occurred_at=row.occurred_at,
            text=activity_text(row.kind, role, row.payload),
        )
        for row in rows
    ]
    return items, total


def derive_home_events(
    session: Session, *, org_id: UUID, now: datetime
) -> list[HomeEvent]:
    box_offline: list[HomeEvent] = []
    for agent in session.exec(select(Agent).where(Agent.org_id == org_id)).all():
        if agent_connections.is_online(agent.id):
            continue
        last_seen = agent_connections.last_seen_at(agent.id) or agent.last_seen_at
        if last_seen is None:
            continue
        days = (now - last_seen).days
        if days <= BOX_OFFLINE_DAYS:
            continue
        box_offline.append(
            HomeEvent(
                kind=HomeEventKind.box_offline,
                text=f"{agent.display_name} has been offline for {days} days",
                occurred_at=last_seen,
            )
        )
    box_offline.sort(key=lambda event: event.occurred_at)

    idle_cutoff = now - timedelta(days=MEMBER_IDLE_DAYS)
    # Idle is a SQL predicate over `users`; a member who has never signed in is
    # idle from the day the account was made. Longest idle first, so the
    # reference date doubles as the sort key.
    idle_reference = func.coalesce(User.last_login_at, User.created_at)
    member_idle = [
        HomeEvent(
            kind=HomeEventKind.member_idle,
            text=f"{user.email} has not signed in for "
            f"{(now - (user.last_login_at or user.created_at)).days} days",
            occurred_at=user.last_login_at or user.created_at,
        )
        for user in session.exec(
            select(User)
            .where(User.org_id == org_id)
            .where(
                or_(
                    User.last_login_at.is_(None),
                    User.last_login_at < idle_cutoff,
                )
            )
            .order_by(idle_reference.asc())
        ).all()
    ]

    baseline_at = session.exec(
        select(func.min(ScanRecord.timestamp))
        .where(ScanRecord.org_id == org_id)
        .where(ScanRecord.status == "completed")
    ).one()
    recent_cutoff = now - timedelta(days=MACHINE_FIRST_SEEN_RECENT_DAYS)
    machine_query = (
        select(HostRecord)
        .where(HostRecord.org_id == org_id)
        .where(HostRecord.first_seen_at >= recent_cutoff)
    )
    if baseline_at is not None:
        machine_query = machine_query.where(HostRecord.first_seen_at > baseline_at)
    machines = [
        HomeEvent(
            kind=HomeEventKind.machine_first_seen,
            text=f"New machine joined the network: {host.hostname}",
            occurred_at=host.first_seen_at,
        )
        for host in session.exec(
            machine_query.order_by(HostRecord.first_seen_at.desc())
        ).all()
    ]

    return box_offline + member_idle + machines


def build_notices(
    latest_scan: ScanSummary | None,
    latest_successful_scan: ScanSummary | None,
    now: datetime,
) -> list[HomeNotice]:
    notices: list[HomeNotice] = []
    if latest_scan is not None and latest_scan.status == "failed":
        notices.append(
            HomeNotice(
                kind="failed_scan", text="Last night's scan didn't finish."
            )
        )
    if latest_successful_scan is not None:
        days = (now - latest_successful_scan.timestamp).days
        if days > STALE_COVERAGE_DAYS:
            notices.append(
                HomeNotice(
                    kind="stale_coverage",
                    text=f"No successful scan in {days} days.",
                    days=days,
                )
            )
    return notices


def read_home_snapshot(
    session: Session,
    *,
    org_id: UUID,
    role: str,
    attention_page: int,
    events_page: int,
    activity_page: int,
    now: datetime,
) -> HomeSnapshot:
    latest_scan = _latest_scan(session, org_id=org_id, status=None)
    latest_successful_scan = _latest_scan(session, org_id=org_id, status="completed")

    attention = page_attention(
        session,
        org_id=org_id,
        scan_id=latest_scan.scan_id if latest_scan else None,
        page=attention_page,
    )
    notices = build_notices(latest_scan, latest_successful_scan, now)
    review_count = attention.total + len(notices)

    if latest_scan is None:
        review_state = "blank"
    elif review_count == 0:
        review_state = "clear"
    else:
        review_state = "pending"

    activity, activity_total = list_org_activity(
        session,
        org_id=org_id,
        role=role,
        page=activity_page,
        per_page=HOME_ACTIVITY_PER_PAGE,
    )

    all_events = derive_home_events(session, org_id=org_id, now=now)
    events_offset = (events_page - 1) * HOME_EVENTS_PER_PAGE
    events_data = all_events[events_offset : events_offset + HOME_EVENTS_PER_PAGE]

    return HomeSnapshot(
        review_state=review_state,
        review_count=review_count,
        latest_successful_scan=latest_successful_scan,
        notices=notices,
        attention=attention,
        events=HomeEventsPage(
            data=events_data, total=len(all_events), page=events_page
        ),
        activity=HomeActivityPage(
            data=activity, total=activity_total, page=activity_page
        ),
    )


def _latest_scan(
    session: Session, *, org_id: UUID, status: str | None
) -> ScanSummary | None:
    page = read.list_scans(
        session, org_id=org_id, page=1, per_page=1, status=status
    )
    return page.data[0] if page.data else None
