from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.models.command import Command
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentCommandFrame
from api.services import agent_connections, commands
from sqlmodel import Session, select

T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)


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


def test_deliver_send_failure_expires_without_scan(
    administrative_session: Session, provisioned_agent, seeded_org
):
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()
    ws.send_text.side_effect = RuntimeError("dead socket")

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        with pytest.raises(commands.DeviceOfflineError):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    # A WebSocket that raised on send is already closed: one attempt, no retry.
    assert ws.send_text.await_count == 1
    administrative_session.refresh(command)
    assert command.status == "expired"
    assert command.scan_id is None
    assert command.delivered_at is None
    assert administrative_session.exec(select(ScanRecord)).all() == []


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
    assert command.scan_id is None
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_deliver_leaves_no_scan_when_command_expired_during_send(
    administrative_session: Session, provisioned_agent, seeded_org
):
    """The sweeper expires the command while `deliver` awaits the socket send.

    The post-send UPDATE then matches no row. Without the rowcount check the
    flushed stub scan would still commit, orphaning a `pending` scan against a
    command that says `expired` — and tripping the `scan_id is not None` assert
    in the router's response builder.
    """
    command = _seed_queued_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
    )
    ws = AsyncMock()

    async def expire_mid_send(_payload: str) -> None:
        # Stand in for the concurrent sweeper: the row leaves `queued` between
        # the send and the UPDATE that would have marked it delivered.
        commands._expire_queued_command(administrative_session, command.id)

    ws.send_text.side_effect = expire_mid_send

    async def run() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)
        with pytest.raises(commands.DeviceOfflineError):
            await commands.deliver(
                administrative_session, command=command, now=T0
            )

    asyncio.run(run())

    ws.send_text.assert_awaited_once()
    administrative_session.refresh(command)
    assert command.status == "expired"
    assert command.scan_id is None
    assert command.delivered_at is None
    assert administrative_session.exec(select(ScanRecord)).all() == []
