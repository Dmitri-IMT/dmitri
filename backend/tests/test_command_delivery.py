from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentCommandFrame
from api.services import activity, agent_connections, agent_presence, commands
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect, WebSocketState

T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
STALE = T0 - timedelta(minutes=20)


def _activity_rows(
    session: Session, org_id, kind: str | None = None
) -> list[ActivityRecord]:
    statement = select(ActivityRecord).where(ActivityRecord.org_id == org_id)
    if kind is not None:
        statement = statement.where(ActivityRecord.kind == kind)
    return list(session.exec(statement).all())


def _seed_queued_command(
    session: Session, *, org_id, agent_id
) -> Command:
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="queued",
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def test_deliver_success_sets_delivered_at_and_stub_scan(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()

    async def assert_delivery_is_durable(_payload: str) -> None:
        administrative_session.refresh(command)
        assert command.status == "delivered"
        assert command.scan_id is not None

    ws.send_text.side_effect = assert_delivery_is_durable

    async def run() -> Command:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        return await commands.deliver(
            administrative_session, command=command, now=T0
        )

    delivered = asyncio.run(run())

    ws.send_text.assert_awaited_once()
    frame = AgentCommandFrame.model_validate_json(ws.send_text.await_args.args[0])
    assert frame.type == "command"
    assert frame.command_id == command.id
    assert frame.scan_mode == "standard"
    assert frame.subnet == "192.168.1.0/24"
    assert frame.scan_id == delivered.scan_id

    assert delivered.status == "delivered"
    assert delivered.delivered_at == T0
    assert delivered.scan_id is not None

    scan = administrative_session.get(ScanRecord, delivered.scan_id)
    assert scan is not None
    assert scan.org_id == seeded_org.id
    assert scan.timestamp == T0
    assert scan.subnet == "192.168.1.0/24"
    assert scan.scan_mode == "standard"
    assert scan.status == "pending"
    assert scan.agent_id == provisioned_agent.id

    started = _activity_rows(
        administrative_session, seeded_org.id, kind="scan_started"
    )
    assert len(started) == 1
    assert started[0].subject_id == delivered.scan_id
    assert started[0].actor_user_id is None
    assert started[0].payload == {"scan_mode": "standard"}


def test_deliver_preserves_nspi_options_in_frame(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = Command(
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_mode="nspi",
        subnet="192.168.1.0/24",
        nspi_options={"version": 1, "submode": "read_only_mapping"},
        status="queued",
    )
    administrative_session.add(command)
    administrative_session.commit()
    administrative_session.refresh(command)
    ws = AsyncMock()

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        await commands.deliver(administrative_session, command=command, now=T0)

    asyncio.run(run())

    frame = AgentCommandFrame.model_validate_json(ws.send_text.await_args.args[0])
    assert frame.nspi_options is not None
    assert frame.nspi_options.submode == "read_only_mapping"


@pytest.mark.parametrize(
    "send_error",
    [
        WebSocketDisconnect(code=1006),
        OSError("broken pipe"),
        RuntimeError('Cannot call "send" once a close message has been sent.'),
    ],
)
def test_deliver_send_failure_keeps_durable_delivery(
    administrative_session: Session,
    provisioned_agent,
    seeded_org,
    send_error: BaseException,
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()
    ws.send_text.side_effect = send_error

    async def run() -> Command:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        return await commands.deliver(
            administrative_session, command=command, now=T0
        )

    delivered = asyncio.run(run())

    assert ws.send_text.await_count == 1
    assert delivered.status == "delivered"
    assert delivered.scan_id is not None
    assert delivered.delivered_at == T0
    administrative_session.refresh(command)
    assert command.status == "delivered"
    assert command.error_code is None
    assert command.scan_id is not None
    assert command.delivered_at == T0
    assert administrative_session.get(ScanRecord, command.scan_id) is not None


def test_deliver_send_bug_is_not_treated_as_offline(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()
    ws.send_text.side_effect = ValueError("bad frame")

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        with pytest.raises(ValueError, match="bad frame"):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    administrative_session.refresh(command)
    assert command.status == "delivered"


def test_deliver_ignores_activity_failure_before_sending(
    administrative_session: Session,
    provisioned_agent,
    seeded_org,
    monkeypatch,
    caplog,
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()

    def fail_activity(*_args, **_kwargs) -> None:
        raise SQLAlchemyError("activity insert failed")

    async def assert_delivery_is_durable(_payload: str) -> None:
        administrative_session.refresh(command)
        assert command.status == "delivered"
        assert command.scan_id is not None

    monkeypatch.setattr(activity, "append_activity", fail_activity)
    ws.send_text.side_effect = assert_delivery_is_durable

    async def run() -> Command:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        return await commands.deliver(
            administrative_session, command=command, now=T0
        )

    delivered = asyncio.run(run())

    ws.send_text.assert_awaited_once()
    assert delivered.status == "delivered"
    assert delivered.scan_id is not None
    assert administrative_session.get(ScanRecord, delivered.scan_id) is not None
    assert _activity_rows(administrative_session, seeded_org.id) == []
    assert "Failed to append scan activity" in caplog.text


def test_deliver_no_socket_raises_offline_without_awaiting_send(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    decoy_ws = AsyncMock()

    async def run() -> None:
        await agent_connections.register(uuid4(), decoy_ws, now=T0)
        with pytest.raises(commands.DeviceOfflineError):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    decoy_ws.send_text.assert_not_awaited()
    administrative_session.refresh(command)
    assert command.status == "expired"
    # The same transition the sweep's `queued` branch takes records the same
    # reason, so a command expired at dispatch is not the one silent record.
    assert command.error_code == "device_offline"
    assert command.scan_id is None
    assert administrative_session.exec(select(ScanRecord)).all() == []
    assert _activity_rows(administrative_session, seeded_org.id) == []


def test_sweep_expired_queued_writes_no_activity(
    administrative_session: Session, seeded_org
):
    agent = Agent(
        org_id=seeded_org.id,
        display_name="stale-agent",
        public_key=b"\x01" * 32,
        last_seen_at=STALE,
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent.id,
    )

    swept = commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    assert swept == 1
    assert _activity_rows(administrative_session, seeded_org.id) == []


def test_apply_status_failed_writes_scan_failed_once(
    administrative_session: Session, provisioned_agent, seeded_org
):
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="quick",
        status="pending",
    )
    administrative_session.add(scan)
    administrative_session.commit()
    command = Command(
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        scan_id=scan.scan_id,
        scan_mode="quick",
        subnet="192.168.1.0/24",
        status="running",
    )
    administrative_session.add(command)
    administrative_session.commit()

    applied = commands.apply_status(
        administrative_session,
        agent_id=provisioned_agent.id,
        command_id=command.id,
        status="failed",
        now=T0,
        error_code="agent_disconnected",
    )

    assert applied is True
    failed = _activity_rows(
        administrative_session, seeded_org.id, kind="scan_failed"
    )
    assert len(failed) == 1
    assert failed[0].subject_id == scan.scan_id
    assert failed[0].payload == {"scan_mode": "quick"}


def test_sweep_stale_failed_scan_activity_is_idempotent(
    administrative_session: Session, seeded_org
):
    agent = Agent(
        org_id=seeded_org.id,
        display_name="stale-agent",
        public_key=b"\x01" * 32,
        last_seen_at=STALE,
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=seeded_org.id,
        agent_id=agent.id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    administrative_session.add(scan)
    administrative_session.commit()
    command = Command(
        org_id=seeded_org.id,
        agent_id=agent.id,
        scan_id=scan.scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status="delivered",
    )
    administrative_session.add(command)
    administrative_session.commit()

    commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )
    commands.sweep_stale_commands(
        administrative_session, now=T0, grace_seconds=900
    )

    failed = _activity_rows(
        administrative_session, seeded_org.id, kind="scan_failed"
    )
    assert len(failed) == 1


def test_deliver_cannot_be_expired_during_send(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()

    async def expire_mid_send(_payload: str) -> None:
        commands._expire_queued_command(administrative_session, command.id)

    ws.send_text.side_effect = expire_mid_send

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        await commands.deliver(administrative_session, command=command, now=T0)

    asyncio.run(run())

    ws.send_text.assert_awaited_once()
    administrative_session.refresh(command)
    assert command.status == "delivered"
    assert command.scan_id is not None
    assert command.delivered_at == T0
    assert administrative_session.get(ScanRecord, command.scan_id) is not None


def test_deliver_to_revoked_agent_closes_socket_without_sending(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    provisioned_agent.revoked_at = T0
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    ws = AsyncMock()
    ws.application_state = WebSocketState.CONNECTED

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        with pytest.raises(commands.DeviceOfflineError):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    ws.send_text.assert_not_awaited()
    ws.close.assert_awaited_once_with(
        code=agent_connections.CLOSE_REVOKED, reason="revoked"
    )
    administrative_session.refresh(command)
    assert command.status == "expired"
    assert command.error_code == "device_offline"
    assert command.scan_id is None
    assert command.delivered_at is None
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_deliver_propagates_failed_revocation_read_without_sending(
    administrative_session: Session, provisioned_agent, seeded_org, monkeypatch
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()

    def boom(session, agent_id):
        raise RuntimeError("revocation read failed")

    monkeypatch.setattr(agent_presence, "agent_is_revoked", boom)

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        with pytest.raises(RuntimeError, match="revocation read failed"):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    ws.send_text.assert_not_awaited()
    administrative_session.refresh(command)
    assert command.status == "queued"
    assert administrative_session.exec(select(ScanRecord)).all() == []
