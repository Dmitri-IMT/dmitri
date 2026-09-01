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
from starlette.websockets import WebSocketDisconnect, WebSocketState

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
            "available_subnets": [
                {
                    "interface": "eth0",
                    "cidr": "10.0.0.0/24",
                    "is_default_route": False,
                },
                {
                    "interface": "wlan0",
                    "cidr": "192.168.1.0/24",
                    "is_default_route": True,
                },
            ],
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


def _agent_stub(*, revoked_at: datetime | None = None) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.revoked_at = revoked_at
    agent.last_seen_at = T0
    return agent


def _tracking_session_factory(
    *, agent: MagicMock | None = None, get_error=None, configure=None
):
    open_sessions: list[MagicMock] = []
    closed_sessions: list[MagicMock] = []
    loaded = _agent_stub() if agent is None else agent

    def factory() -> MagicMock:
        session = MagicMock(spec=Session)
        if get_error is not None:
            session.get.side_effect = get_error
        else:
            session.get.return_value = loaded
        if configure is not None:
            configure(session)
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
    assert [(s.interface, s.is_default_route) for s in hello[1]] == [
        ("eth0", False),
        ("wlan0", True),
    ]
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
    ws.close.assert_not_awaited()
    assert agent_connections.get_hello(provisioned_agent.id) is None
    assert agent_connections.last_seen_at(provisioned_agent.id) == T1
    with Session(migrated_database) as session:
        agent = session.get(Agent, provisioned_agent.id)
        assert agent is not None
        assert agent.last_seen_at == T1


INVALID_FRAMES = [
    "not json",
    json.dumps("bare string"),
    json.dumps({"status": "running"}),
    json.dumps({"type": "hello", "agent_version": "0.1.0"}),
    json.dumps({"type": "nope"}),
    json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [
                {"interface": "eth0", "cidr": "10.0.0.0/24"},
            ],
        }
    ),
    json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [
                {
                    "interface": "eth0",
                    "cidr": "10.0.0.0/24",
                    "is_default_route": None,
                },
            ],
        }
    ),
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
]


@pytest.mark.parametrize(
    "raw_text, expected",
    [
        ("{not json", "invalid JSON"),
        ("[1, 2]", "invalid frame"),
        (json.dumps({"type": "hello"}), "invalid hello frame"),
        (json.dumps({"type": "status"}), "invalid status frame"),
        (json.dumps({"type": "command"}), "invalid inbound frame"),
        (json.dumps({"agent_version": "1.0.0"}), "missing type"),
        (json.dumps({"type": "goodbye"}), "unknown frame type"),
    ],
)
def test_parse_frame_rejects_with_the_published_message(raw_text: str, expected: str):
    parsed = agent_ws._parse_frame(raw_text)

    assert isinstance(parsed, agent_ws._Reject)
    assert parsed.message == expected


def test_parse_frame_accepts_hello_and_status_without_io():
    hello = agent_ws._parse_frame(_hello_payload())
    status = agent_ws._parse_frame(_status_payload())

    assert isinstance(hello, agent_ws._Hello)
    assert hello.frame.agent_version
    assert isinstance(status, agent_ws._Status)
    assert status.frame.command_id == COMMAND_ID


@pytest.mark.parametrize("raw_text", INVALID_FRAMES)
def test_invalid_frames_send_error_and_keep_socket_usable(raw_text: str):
    ws = AsyncMock()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(raw_text, session_factory, ws, agent_id=AGENT_ID))

    error = _error_from_mock(ws)
    assert error.type == "error"
    assert error.message
    assert len(session_factory.open_sessions) == 1
    assert session_factory.closed_sessions == session_factory.open_sessions
    assert session_factory.open_sessions[0].get.call_count == 1
    ws.close.assert_not_awaited()

    ws.send_text.reset_mock()
    asyncio.run(_handle(_hello_payload(), session_factory, ws, agent_id=AGENT_ID))
    ws.send_text.assert_not_awaited()
    assert agent_connections.get_hello(AGENT_ID) is not None
    assert len(session_factory.open_sessions) == 2
    assert session_factory.closed_sessions == session_factory.open_sessions


def _feed(ws: AsyncMock, frames: list[str], *, before_each=None) -> None:
    """Drive run_agent_channel from `frames`, then disconnect.

    The channel reads with receive_text() and guards on application_state, so a
    bare AsyncMock would exit before the first frame. `before_each` runs ahead
    of every frame after the first, for asserting between-frame state.
    """
    ws.application_state = WebSocketState.CONNECTED
    pending = list(frames)

    async def receive_text() -> str:
        if before_each is not None and len(pending) < len(frames):
            before_each()
        if not pending:
            raise WebSocketDisconnect(code=1000)
        return pending.pop(0)

    ws.receive_text = receive_text


def test_two_frames_use_distinct_sessions_closed_per_frame():
    ws = AsyncMock()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    seen: list[int] = []

    def between_frames() -> None:
        # Only meaningful before the second frame: the first frame's session
        # must already be open and closed by the time the next read happens.
        if seen:
            return
        seen.append(1)
        assert len(session_factory.open_sessions) == 1
        assert session_factory.closed_sessions == session_factory.open_sessions

    _feed(
        ws,
        [_hello_payload(), _status_payload()],
        before_each=between_frames,
    )

    asyncio.run(agent_ws.run_agent_channel(ws, session_factory, agent_id=AGENT_ID))

    assert seen == [1]

    assert len(session_factory.open_sessions) == 2
    assert (
        session_factory.open_sessions[0] is not session_factory.open_sessions[1]
    )
    assert session_factory.closed_sessions == session_factory.open_sessions
    ws.close.assert_not_awaited()


def test_no_session_outlives_ws_loop():
    ws = AsyncMock()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    _feed(ws, [_hello_payload(), _status_payload()])

    asyncio.run(agent_ws.run_agent_channel(ws, session_factory, agent_id=AGENT_ID))

    assert len(session_factory.open_sessions) == 2
    assert session_factory.closed_sessions == session_factory.open_sessions
    ws.close.assert_not_awaited()


def test_run_agent_channel_processes_frames_and_survives_errors(
    migrated_database: Engine, provisioned_agent: Agent
):
    ws = AsyncMock()
    asyncio.run(agent_connections.register(provisioned_agent.id, ws, now=T0))

    _feed(ws, [_hello_payload(), "not json", _status_payload()])

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


def _connected_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.application_state = WebSocketState.CONNECTED
    return ws


def test_revoked_status_frame_writes_no_transition_and_closes(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        agent_ws, "apply_status", lambda *a, **k: calls.append((a, k)) or True
    )
    ws = _connected_ws()
    session_factory = _tracking_session_factory(agent=_agent_stub(revoked_at=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(_status_payload(), session_factory, ws, agent_id=AGENT_ID))

    assert calls == []
    ws.send_text.assert_not_awaited()
    ws.close.assert_awaited_once_with(code=4001, reason="revoked")
    assert session_factory.closed_sessions == session_factory.open_sessions


def test_revoked_hello_frame_leaves_registry_subnets_unchanged():
    ws = _connected_ws()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))
    asyncio.run(
        _handle(
            _hello_payload(), _tracking_session_factory(), ws, agent_id=AGENT_ID
        )
    )
    before = agent_connections.get_hello(AGENT_ID)
    assert before is not None

    revoked_hello = json.dumps(
        {
            "type": "hello",
            "agent_version": "9.9.9",
            "available_subnets": [
                {
                    "interface": "eth9",
                    "cidr": "172.16.0.0/24",
                    "is_default_route": True,
                }
            ],
        }
    )
    asyncio.run(
        _handle(
            revoked_hello,
            _tracking_session_factory(agent=_agent_stub(revoked_at=T0)),
            ws,
            agent_id=AGENT_ID,
        )
    )

    assert agent_connections.get_hello(AGENT_ID) == before
    ws.close.assert_awaited_once_with(code=4001, reason="revoked")


def test_status_frame_loads_the_agent_once():
    ws = _connected_ws()
    session_factory = _tracking_session_factory()
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(_status_payload(), session_factory, ws, agent_id=AGENT_ID))

    session = session_factory.open_sessions[0]
    assert session.get.call_count == 1
    assert session.get.call_args.args[0] is Agent
    ws.close.assert_not_awaited()


def test_status_frame_fails_closed_when_revocation_read_raises(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        agent_ws, "apply_status", lambda *a, **k: calls.append((a, k)) or True
    )
    ws = _connected_ws()
    session_factory = _tracking_session_factory(
        get_error=RuntimeError("database down")
    )
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    with pytest.raises(RuntimeError, match="database down"):
        asyncio.run(_handle(_status_payload(), session_factory, ws, agent_id=AGENT_ID))

    assert calls == []
    ws.close.assert_not_awaited()
    assert session_factory.closed_sessions == session_factory.open_sessions


def _unknown_command(session: MagicMock) -> None:
    session.exec.return_value.first.return_value = None


@pytest.mark.parametrize("raw_text", INVALID_FRAMES)
def test_revoked_invalid_frame_sends_error_then_closes(raw_text: str):
    ws = _connected_ws()
    session_factory = _tracking_session_factory(agent=_agent_stub(revoked_at=T0))
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(raw_text, session_factory, ws, agent_id=AGENT_ID))

    error = _error_from_mock(ws)
    assert error.type == "error"
    ws.close.assert_awaited_once_with(code=4001, reason="revoked")
    assert [call[0] for call in ws.mock_calls] == ["send_text", "close"]
    assert len(session_factory.open_sessions) == 1
    assert session_factory.open_sessions[0].get.call_count == 1
    assert session_factory.closed_sessions == session_factory.open_sessions


def test_unknown_command_id_opens_no_second_session(monkeypatch):
    monkeypatch.setattr(agent_ws, "apply_status", lambda *a, **k: False)
    ws = _connected_ws()
    session_factory = _tracking_session_factory(configure=_unknown_command)
    asyncio.run(agent_connections.register(AGENT_ID, ws, now=T0))

    asyncio.run(_handle(_status_payload(), session_factory, ws, agent_id=AGENT_ID))

    error = _error_from_mock(ws)
    assert error.message == "unknown command_id"
    ws.close.assert_not_awaited()
    assert len(session_factory.open_sessions) == 1
    assert session_factory.closed_sessions == session_factory.open_sessions
