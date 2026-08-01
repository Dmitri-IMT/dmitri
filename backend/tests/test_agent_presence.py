from __future__ import annotations

from datetime import UTC, datetime

import pytest
from api.main import app
from api.models.command import Agent
from api.services import agent_connections, agent_presence
from conftest import ws_upgrade_headers
from sqlalchemy.engine import Engine
from sqlmodel import Session
from starlette.testclient import TestClient

T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 27, 12, 1, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clear_registry():
    agent_connections._registry.clear()
    yield
    agent_connections._registry.clear()


def _ws_path(agent_id) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


def test_touch_agent_last_seen_commits(
    administrative_session: Session, provisioned_agent: Agent
):
    agent_presence.touch_agent_last_seen(
        administrative_session, provisioned_agent.id, T1
    )

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at == T1


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
