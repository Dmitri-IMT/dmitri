from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from api.main import app
from api.models.command import Agent
from api.services import agent_connections, agent_presence
from conftest import ws_upgrade_headers
from sqlalchemy.engine import Engine
from sqlmodel import Session
from starlette.testclient import TestClient

AGENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 27, 12, 1, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_registry():
    agent_connections._registry.clear()
    yield
    agent_connections._registry.clear()


def _ws_path(agent_id) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


def test_mark_connected_sets_connected_at_and_last_seen_at(
    administrative_session: Session, provisioned_agent: Agent
):
    agent_presence.mark_connected(administrative_session, provisioned_agent.id, T1)

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.connected_at == T1
    assert provisioned_agent.last_seen_at == T1


def test_mark_disconnected_clears_connected_at(
    administrative_session: Session, provisioned_agent: Agent
):
    agent_presence.mark_connected(administrative_session, provisioned_agent.id, T1)

    agent_presence.mark_disconnected(administrative_session, provisioned_agent.id)

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.connected_at is None
    assert provisioned_agent.last_seen_at == T1


def test_reconcile_all_clears_stale_connected_at_after_simulated_crash(
    administrative_session: Session, provisioned_agent: Agent
):
    provisioned_agent.connected_at = T1
    provisioned_agent.last_seen_at = T1
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    agent_presence.reconcile_all(administrative_session)

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.connected_at is None
    assert provisioned_agent.last_seen_at == T1


def test_disconnect_clears_connected_at_when_channel_raises(
    migrated_database: Engine,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    monkeypatch: pytest.MonkeyPatch,
):
    connected_during_channel: list[bool] = []

    async def failing_channel(*args, **kwargs):
        with Session(migrated_database) as session:
            agent = session.get(Agent, provisioned_agent.id)
            assert agent is not None
            connected_during_channel.append(agent.connected_at is not None)
        raise RuntimeError("channel failed")

    monkeypatch.setattr(
        "api.routers.agents.run_agent_channel", failing_channel
    )

    private_key, _public_key = agent_keypair
    client = TestClient(app)
    with pytest.raises(RuntimeError, match="channel failed"):
        with client.websocket_connect(
            _ws_path(provisioned_agent.id),
            headers=ws_upgrade_headers(private_key, provisioned_agent.id),
        ) as websocket:
            websocket.receive_text()

    assert connected_during_channel == [True]
    administrative_session.expire(provisioned_agent)
    agent = administrative_session.get(Agent, provisioned_agent.id)
    assert agent is not None
    assert agent.connected_at is None


def test_startup_lifespan_calls_reconcile_all(monkeypatch: pytest.MonkeyPatch):
    calls: list[bool] = []

    def fake_reconcile(session: Session) -> None:
        calls.append(True)

    monkeypatch.setattr("api.main.reconcile_all", fake_reconcile)

    with TestClient(app):
        pass

    assert calls == [True]


def test_agent_is_revoked_tracks_revoked_at(
    administrative_session: Session, provisioned_agent: Agent
):
    assert (
        agent_presence.agent_is_revoked(administrative_session, provisioned_agent.id)
        is False
    )

    provisioned_agent.revoked_at = T1
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    assert (
        agent_presence.agent_is_revoked(administrative_session, provisioned_agent.id)
        is True
    )


def test_touch_unless_revoked_writes_nothing_for_revoked_agent(
    migrated_database: Engine,
    administrative_session: Session,
    provisioned_agent: Agent,
):
    provisioned_agent.last_seen_at = T0
    provisioned_agent.revoked_at = T0
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    revoked = agent_presence.touch_unless_revoked(
        administrative_session, provisioned_agent.id, T1
    )

    assert revoked is True
    with Session(migrated_database) as session:
        agent = session.get(Agent, provisioned_agent.id)
        assert agent is not None
        assert agent.last_seen_at == T0


def test_touch_unless_revoked_bumps_last_seen_at_for_healthy_agent(
    administrative_session: Session, provisioned_agent: Agent
):
    revoked = agent_presence.touch_unless_revoked(
        administrative_session, provisioned_agent.id, T1
    )

    assert revoked is False
    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at == T1


def test_touch_unless_revoked_loads_the_agent_once(provisioned_agent: Agent):
    session = MagicMock(spec=Session)
    session.get.return_value = provisioned_agent

    assert (
        agent_presence.touch_unless_revoked(session, provisioned_agent.id, T1) is False
    )

    assert session.get.call_count == 1


@pytest.mark.parametrize(
    "call",
    [
        lambda session, agent_id: agent_presence.agent_is_revoked(session, agent_id),
        lambda session, agent_id: agent_presence.touch_unless_revoked(
            session, agent_id, T1
        ),
    ],
)
def test_revocation_reads_propagate_read_failures(call):
    session = MagicMock(spec=Session)
    session.get.side_effect = RuntimeError("database down")

    with pytest.raises(RuntimeError, match="database down"):
        call(session, AGENT_ID)


def test_revocation_reads_report_unknown_agent_as_not_revoked(
    administrative_session: Session,
):
    assert (
        agent_presence.agent_is_revoked(administrative_session, AGENT_ID) is False
    )
    assert (
        agent_presence.touch_unless_revoked(administrative_session, AGENT_ID, T1)
        is False
    )


@pytest.mark.parametrize("revoked_at, expected", [(None, False), (T0, True)])
def test_async_touch_unless_revoked_matches_sync(
    migrated_database: Engine,
    administrative_session: Session,
    provisioned_agent: Agent,
    revoked_at,
    expected,
):
    provisioned_agent.revoked_at = revoked_at
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    result = asyncio.run(
        agent_presence.async_touch_unless_revoked(
            partial(Session, migrated_database), provisioned_agent.id, T1
        )
    )

    assert result is expected
