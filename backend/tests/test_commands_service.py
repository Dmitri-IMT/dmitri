from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.services import commands, read
from fastapi.testclient import TestClient
from sqlmodel import Session, select

T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
STALE = T0 - timedelta(minutes=20)


def _activity_rows(
    session: Session, org_id, kind: str | None = None
) -> list[ActivityRecord]:
    statement = select(ActivityRecord).where(ActivityRecord.org_id == org_id)
    if kind is not None:
        statement = statement.where(ActivityRecord.kind == kind)
    return list(session.exec(statement).all())


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_org(session: Session) -> Org:
    org = Org(name=f"org-{uuid4()}")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _seed_agent(
    session: Session, org_id, *, last_seen_at=None, connected_at=None
) -> Agent:
    agent = Agent(
        org_id=org_id,
        display_name=f"agent-{uuid4()}",
        public_key=b"\x01" * 32,
        last_seen_at=last_seen_at,
        connected_at=connected_at,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _seed_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def _seed_command(
    session: Session,
    *,
    org_id,
    agent_id,
    status: str,
    scan_id=None,
    scan_mode: str = "standard",
    created_at: datetime | None = None,
    delivered_at: datetime | None = None,
) -> Command:
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode=scan_mode,
        subnet="192.168.1.0/24",
        status=status,
        delivered_at=delivered_at,
    )
    if created_at is not None:
        command.created_at = created_at
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def test_active_command_for_returns_queued(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
    )

    found = commands.active_command_for(administrative_session, provisioned_agent.id)

    assert found is not None
    assert found.id == command.id


def test_active_command_for_returns_delivered(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="delivered",
        scan_id=scan.scan_id,
    )

    found = commands.active_command_for(administrative_session, provisioned_agent.id)

    assert found is not None
    assert found.id == command.id


def test_cancel_command_rejects_uploading(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="uploading",
        scan_id=scan.scan_id,
    )

    with pytest.raises(commands.CommandNotCancellableError):
        asyncio.run(
            commands.cancel_command(
                administrative_session,
                org_id=seeded_org.id,
                command_id=command.id,
                now=T0,
            )
        )


def test_apply_status_applies_forward_rank(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
        scan_id=scan.scan_id,
    )

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="running",
        now=T0,
    )

    assert applied is True
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "running"
    assert command.started_at == T0
    assert command.delivered_at == T0
    assert scan.status == "accepted"


@pytest.mark.parametrize(
    ("initial_scan_status", "expected_scan_status"),
    [("pending", "cancelled"), ("completed", "completed")],
)
def test_apply_status_cancelled_preserves_completed_scan_and_records_activity(
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    initial_scan_status: str,
    expected_scan_status: str,
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    scan.status = initial_scan_status
    administrative_session.add(scan)
    administrative_session.commit()
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="cancelled",
        now=T0,
    )

    assert applied is True
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "cancelled"
    assert scan.status == expected_scan_status
    cancelled = _activity_rows(
        administrative_session, seeded_org.id, kind="scan_cancelled"
    )
    assert len(cancelled) == 1
    assert cancelled[0].subject_id == scan.scan_id
    assert _activity_rows(administrative_session, seeded_org.id, "scan_failed") == []


def test_apply_status_no_ops_on_duplicate(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    command.started_at = T0
    administrative_session.add(command)
    administrative_session.commit()

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="running",
        now=T0,
    )

    assert applied is False
    administrative_session.refresh(command)
    assert command.status == "running"


def test_apply_status_no_ops_on_backward(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="queued",
        now=T0,
    )

    assert applied is False
    administrative_session.refresh(command)
    assert command.status == "running"


def test_apply_status_does_not_expire_delivered(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="delivered",
        scan_id=scan.scan_id,
    )

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="expired",
        now=T0,
    )

    assert applied is False
    administrative_session.refresh(command)
    assert command.status == "delivered"


def test_apply_status_rejects_non_pi_owned_targets(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
        scan_id=scan.scan_id,
    )

    for status in ("queued", "delivered", "expired"):
        applied = commands.apply_status(
            administrative_session,
            agent_id=provisioned_agent.id,
            command_id=command.id,
            status=status,
            now=T0,
        )
        assert applied is False

    administrative_session.refresh(command)
    assert command.status == "queued"


def test_apply_status_refuses_other_agents_command(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    other = _seed_agent(administrative_session, seeded_org.id)
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=other.id,
        status="queued",
        scan_id=scan.scan_id,
    )

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="running",
        now=T0,
    )

    assert applied is False
    administrative_session.refresh(command)
    assert command.status == "queued"


def test_apply_status_no_ops_on_undelivered_command(
    administrative_session: Session, provisioned_agent: Agent, seeded_org: Org
):
    """A `running` frame that overtakes `deliver`'s commit must not crash.

    The Pi can reply in milliseconds, before the enqueue path commits
    `delivered` — so the frame finds a `queued` command with no `scan_id`.
    Advancing it would violate `ck_commands_scan_id_or_expired`, since only
    `queued`/`expired` may carry a null `scan_id`. The frame is dropped as a
    lost race instead; the Pi's later `uploading`/`done` frames apply normally
    once delivery has set `scan_id`.
    """
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
    )
    assert command.scan_id is None

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="running",
        now=T0,
    )

    assert applied is False
    administrative_session.refresh(command)
    assert command.status == "queued"
    assert command.started_at is None
    assert command.delivered_at is None


def test_sweep_stale_commands_expires_stale_queued(
    administrative_session: Session,
    seeded_org: Org,
    client: TestClient,
    bearer_headers,
):
    agent = _seed_agent(administrative_session, seeded_org.id, last_seen_at=STALE)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="queued",
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    administrative_session.refresh(command)
    assert command.status == "expired"
    assert command.error_code == "device_offline"
    assert command.completed_at is None
    assert command.scan_id is None

    response = client.get(
        f"/api/v1/commands/{command.id}",
        headers=bearer_headers(seeded_org.id, "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "expired"
    assert body["error_code"] == "device_offline"
    assert body["scan_id"] is None


@pytest.mark.parametrize("status", ["delivered", "running", "uploading"])
def test_sweep_stale_commands_fails_stale_non_terminal(
    administrative_session: Session, seeded_org: Org, status: str
):
    agent = _seed_agent(administrative_session, seeded_org.id, last_seen_at=STALE)
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status=status,
        scan_id=scan.scan_id,
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "failed"
    assert command.error_code == "agent_disconnected"
    assert command.completed_at == T0
    assert scan.status == "failed"

    detail = read.get_scan_detail(
        administrative_session, scan.scan_id, org_id=seeded_org.id
    )
    assert detail is not None
    assert detail.status == "failed"
    assert detail.error_code == "agent_disconnected"
    assert detail.command_id == command.id


def test_sweep_stale_commands_leaves_connected_queued_past_mode_limit(
    administrative_session: Session, seeded_org: Org
):
    agent = _seed_agent(
        administrative_session,
        seeded_org.id,
        last_seen_at=T0,
        connected_at=T0,
    )
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="queued",
        scan_mode="quick",
        created_at=T0 - timedelta(seconds=10801),
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 0
    administrative_session.refresh(command)
    assert command.status == "queued"
    assert command.scan_id is None


@pytest.mark.parametrize(
    ("scan_mode", "max_duration_seconds"),
    [
        ("quick", 10800),
        ("standard", 28800),
        ("extensive", 57600),
        ("nspi", 21600),
        ("max", 93600),
    ],
)
def test_sweep_stale_commands_expires_connected_agent_past_mode_limit(
    administrative_session: Session,
    seeded_org: Org,
    scan_mode: str,
    max_duration_seconds: int,
):
    agent = _seed_agent(
        administrative_session,
        seeded_org.id,
        last_seen_at=STALE,
        connected_at=T0,
    )
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="running",
        scan_id=scan.scan_id,
        scan_mode=scan_mode,
        delivered_at=T0 - timedelta(seconds=max_duration_seconds + 1),
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "failed"
    assert command.error_code == "scan_timeout"
    assert command.completed_at == T0
    assert scan.status == "failed"
    failed = _activity_rows(
        administrative_session, seeded_org.id, kind="scan_failed"
    )
    assert len(failed) == 1
    assert failed[0].subject_id == scan.scan_id
    assert failed[0].payload == {"scan_mode": scan_mode}


def test_sweep_stale_commands_leaves_connected_agent_command_inside_mode_limit(
    administrative_session: Session, seeded_org: Org
):
    agent = _seed_agent(
        administrative_session,
        seeded_org.id,
        last_seen_at=STALE,
        connected_at=T0,
    )
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="running",
        scan_id=scan.scan_id,
        scan_mode="quick",
        delivered_at=T0 - timedelta(seconds=10800),
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 0
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "running"
    assert scan.status == "pending"


def test_sweep_stale_commands_times_from_delivery_not_enqueue(
    administrative_session: Session, seeded_org: Org
):
    agent = _seed_agent(
        administrative_session,
        seeded_org.id,
        last_seen_at=T0,
        connected_at=T0,
    )
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="running",
        scan_id=scan.scan_id,
        scan_mode="quick",
        created_at=T0 - timedelta(seconds=10801),
        delivered_at=T0 - timedelta(seconds=60),
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 0
    administrative_session.refresh(command)
    assert command.status == "running"


def test_sweep_stale_commands_disconnect_reason_wins_past_mode_limit(
    administrative_session: Session, seeded_org: Org
):
    agent = _seed_agent(administrative_session, seeded_org.id, last_seen_at=STALE)
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="running",
        scan_id=scan.scan_id,
        scan_mode="quick",
        delivered_at=T0 - timedelta(seconds=10801),
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    administrative_session.refresh(command)
    assert command.status == "failed"
    assert command.error_code == "agent_disconnected"


def test_sweep_stale_commands_mirrors_scan_status_for_delivered(
    administrative_session: Session, seeded_org: Org
):
    agent = _seed_agent(administrative_session, seeded_org.id, last_seen_at=STALE)
    scan = _seed_scan(administrative_session, seeded_org.id)
    _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
        status="delivered",
        scan_id=scan.scan_id,
    )

    commands.sweep_stale_commands(administrative_session, now=T0, grace_seconds=900)

    administrative_session.refresh(scan)
    assert scan.status == "failed"
