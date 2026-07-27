from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from api.models.command import Agent
from api.schemas.agent_frames import AgentErrorFrame
from api.services import agent_connections, agent_ws
from sqlmodel import Session

AGENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")
T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 27, 12, 1, 0, tzinfo=UTC)
T1_NAIVE = T1.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def clear_registry():
    agent_connections._registry.clear()
    yield
    agent_connections._registry.clear()


def _hello_payload() -> str:
    return json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [{"interface": "eth0", "cidr": "10.0.0.0/24"}],
        }
    )


def _status_payload(*, status: str = "running") -> str:
    return json.dumps(
        {
            "type": "status",
            "command_id": str(COMMAND_ID),
            "status": status,
        }
    )


async def _handle(
    raw_text: str,
    session: MagicMock | Session,
    ws: AsyncMock,
    *,
    agent_id: UUID,
) -> None:
    await agent_ws.handle_agent_frame(
        session,
        ws,
        agent_id=agent_id,
        raw_text=raw_text,
        now=T1,
    )


def _error_from_mock(ws: AsyncMock) -> AgentErrorFrame:
    ws.send_text.assert_awaited_once()
    return AgentErrorFrame.model_validate_json(ws.send_text.await_args.args[0])


def test_touch_agent_last_seen_commits(
    administrative_session: Session, provisioned_agent: Agent
):
    agent_ws.touch_agent_last_seen(administrative_session, provisioned_agent.id, T1)

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at == T1_NAIVE


def test_hello_sets_registry_and_bumps_db_last_seen(
    administrative_session: Session, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    agent_id = provisioned_agent.id
    asyncio.run(
        _handle(_hello_payload(), administrative_session, ws, agent_id=agent_id)
    )

    ws.send_text.assert_not_awaited()
    hello = agent_connections.get_hello(provisioned_agent.id)
    assert hello is not None
    assert hello[0] == "0.2.0"
    assert hello[1][0].interface == "eth0"
    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at == T1_NAIVE


def test_status_touches_without_prior_hello(
    administrative_session: Session, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    agent_id = provisioned_agent.id
    asyncio.run(
        _handle(_status_payload(), administrative_session, ws, agent_id=agent_id)
    )

    ws.send_text.assert_not_awaited()
    assert agent_connections.get_hello(provisioned_agent.id) is None
    assert agent_connections.last_seen_at(provisioned_agent.id) == T1
    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at == T1_NAIVE


@pytest.mark.parametrize(
    "raw_text",
    [
        "not json",
        json.dumps("bare string"),
        json.dumps({"status": "running"}),
        json.dumps({"type": "hello", "agent_version": "0.1.0"}),
        json.dumps({"type": "nope"}),
        json.dumps(
            {
                "type": "status",
                "command_id": str(COMMAND_ID),
                "status": "queued",
            }
        ),
        json.dumps(
            {
                "type": "command",
                "command_id": str(COMMAND_ID),
                "scan_id": str(COMMAND_ID),
                "scan_mode": "standard",
                "subnet": "10.0.0.0/24",
            }
        ),
    ],
)
def test_invalid_frames_send_error_and_keep_socket_usable(raw_text: str):
    ws = AsyncMock()
    session = MagicMock()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(raw_text, session, ws, agent_id=AGENT_ID))

    error = _error_from_mock(ws)
    assert error.type == "error"
    assert error.message

    ws.send_text.reset_mock()
    asyncio.run(_handle(_hello_payload(), session, ws, agent_id=AGENT_ID))
    ws.send_text.assert_not_awaited()
    assert agent_connections.get_hello(AGENT_ID) is not None


def test_run_agent_channel_processes_frames_and_survives_errors(
    administrative_session: Session, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    async def frames():
        yield _hello_payload()
        yield "not json"
        yield _status_payload()

    ws.iter_text = frames

    asyncio.run(
        agent_ws.run_agent_channel(
            ws, administrative_session, agent_id=provisioned_agent.id
        )
    )

    assert ws.send_text.await_count == 1
    error = AgentErrorFrame.model_validate_json(ws.send_text.await_args.args[0])
    assert error.type == "error"
    assert agent_connections.get_hello(provisioned_agent.id) is not None
    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at is not None
