from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.services import commands
from sqlmodel import Session

T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
STALE = T0 - timedelta(minutes=20)


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
) -> Command:
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status=status,
    )
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
    administrative_session: Session, seeded_org: Org
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
    assert command.completed_at is None


def test_sweep_stale_commands_fails_stale_non_terminal(
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
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "failed"
    assert command.completed_at == T0
    assert scan.status == "failed"


def test_sweep_stale_commands_leaves_connected_agent_command(
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
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 0
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "running"
    assert scan.status == "pending"


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
