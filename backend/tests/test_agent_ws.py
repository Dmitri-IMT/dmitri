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
from sqlalchemy.engine import Engine
from sqlmodel import Session

AGENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")
T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 27, 12, 1, 0, tzinfo=UTC)


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


def _engine_session_factory(engine: Engine):
    return lambda: Session(engine)


async def _handle(
    raw_text: str,
    session_factory,
    ws: AsyncMock,
    *,
    agent_id: UUID,
) -> None:
    await agent_ws.handle_agent_frame(
        session_factory,
        ws,
        agent_id=agent_id,
        raw_text=raw_text,
        now=T1,
    )


def _error_from_mock(ws: AsyncMock) -> AgentErrorFrame:
    ws.send_text.assert_awaited_once()
    return AgentErrorFrame.model_validate_json(ws.send_text.await_args.args[0])


def _tracking_session_factory():
    open_sessions: list[MagicMock] = []
    closed_sessions: list[MagicMock] = []

    def factory() -> MagicMock:
        session = MagicMock(spec=Session)
        open_sessions.append(session)

        def close() -> None:
            closed_sessions.append(session)

        session.close = close
        return session

    factory.open_sessions = open_sessions
    factory.closed_sessions = closed_sessions
    return factory


def test_hello_sets_registry_and_bumps_db_last_seen(
    migrated_database: Engine, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    agent_id = provisioned_agent.id
    asyncio.run(
        _handle(
            _hello_payload(),
            _engine_session_factory(migrated_database),
            ws,
            agent_id=agent_id,
        )
    )

    ws.send_text.assert_not_awaited()
    hello = agent_connections.get_hello(provisioned_agent.id)
    assert hello is not None
    assert hello[0] == "0.2.0"
    assert hello[1][0].interface == "eth0"
    with Session(migrated_database) as session:
        agent = session.get(Agent, provisioned_agent.id)
        assert agent is not None
        assert agent.last_seen_at == T1


def test_status_touches_without_prior_hello(
    migrated_database: Engine, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    agent_id = provisioned_agent.id
    asyncio.run(
        _handle(
            _status_payload(),
            _engine_session_factory(migrated_database),
            ws,
            agent_id=agent_id,
        )
    )

    error = _error_from_mock(ws)
    assert error.message == "unknown command_id"
    assert agent_connections.get_hello(provisioned_agent.id) is None
    assert agent_connections.last_seen_at(provisioned_agent.id) == T1
    with Session(migrated_database) as session:
        agent = session.get(Agent, provisioned_agent.id)
        assert agent is not None
        assert agent.last_seen_at == T1


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
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(raw_text, session_factory, ws, agent_id=AGENT_ID))

    error = _error_from_mock(ws)
    assert error.type == "error"
    assert error.message
    assert session_factory.open_sessions == []
    assert session_factory.closed_sessions == []

    ws.send_text.reset_mock()
    asyncio.run(_handle(_hello_payload(), session_factory, ws, agent_id=AGENT_ID))
    ws.send_text.assert_not_awaited()
    assert agent_connections.get_hello(AGENT_ID) is not None
    assert len(session_factory.open_sessions) == 1
    assert session_factory.closed_sessions == session_factory.open_sessions


def test_two_frames_use_distinct_sessions_closed_per_frame():
    ws = AsyncMock()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    async def frames():
        yield _hello_payload()
        assert len(session_factory.open_sessions) == 1
        assert session_factory.closed_sessions == session_factory.open_sessions
        yield _status_payload()

    ws.iter_text = frames

    asyncio.run(agent_ws.run_agent_channel(ws, session_factory, agent_id=AGENT_ID))

    assert len(session_factory.open_sessions) == 2
    assert (
        session_factory.open_sessions[0] is not session_factory.open_sessions[1]
    )
    assert session_factory.closed_sessions == session_factory.open_sessions


def test_no_session_outlives_ws_loop():
    ws = AsyncMock()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    async def frames():
        yield _hello_payload()
        yield _status_payload()

    ws.iter_text = frames

    asyncio.run(agent_ws.run_agent_channel(ws, session_factory, agent_id=AGENT_ID))

    assert len(session_factory.open_sessions) == 2
    assert session_factory.closed_sessions == session_factory.open_sessions


def test_run_agent_channel_processes_frames_and_survives_errors(
    migrated_database: Engine, provisioned_agent: Agent
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
            ws,
            _engine_session_factory(migrated_database),
            agent_id=provisioned_agent.id,
        )
    )

    assert ws.send_text.await_count == 2
    first = AgentErrorFrame.model_validate_json(
        ws.send_text.await_args_list[0].args[0]
    )
    second = AgentErrorFrame.model_validate_json(
        ws.send_text.await_args_list[1].args[0]
    )
    assert first.message == "invalid JSON"
    assert second.message == "unknown command_id"
    assert agent_connections.get_hello(provisioned_agent.id) is not None
    with Session(migrated_database) as session:
        agent = session.get(Agent, provisioned_agent.id)
        assert agent is not None
        assert agent.last_seen_at is not None
