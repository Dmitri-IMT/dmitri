from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org
from api.services import agent_connections
from fastapi.testclient import TestClient
from sqlmodel import Session
from starlette.websockets import WebSocketState


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _path(agent_id, action: str) -> str:
    return f"/api/v1/agents/{agent_id}/{action}"


def _other_org_agent(session: Session) -> Agent:
    org = Org(name=f"other-{uuid4()}")
    session.add(org)
    session.flush()
    agent = Agent(
        org_id=org.id,
        display_name="Other Agent",
        public_key=b"\x05" * 32,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def test_revoke_sets_date_and_closes_live_socket(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    socket = AsyncMock()
    socket.application_state = WebSocketState.CONNECTED
    asyncio.run(
        agent_connections.register(
            provisioned_agent.id, socket, now=provisioned_agent.created_at
        )
    )

    response = client.post(
        _path(provisioned_agent.id, "revoke"),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 200
    assert response.json()["revoked_at"] is not None
    socket.close.assert_awaited_once_with(code=4001, reason="revoked")
    administrative_session.expire_all()
    stored = administrative_session.get(Agent, provisioned_agent.id)
    assert stored.revoked_at is not None


def test_revoke_and_restore_are_idempotent_and_preserve_device_fields(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.target_subnet = "192.168.1.0/24"
    administrative_session.add(provisioned_agent)
    administrative_session.commit()
    headers = bearer_headers(seeded_org.id, "admin")

    first = client.post(_path(provisioned_agent.id, "revoke"), headers=headers)
    repeated = client.post(_path(provisioned_agent.id, "revoke"), headers=headers)
    restored = client.post(_path(provisioned_agent.id, "restore"), headers=headers)
    repeated_restore = client.post(
        _path(provisioned_agent.id, "restore"), headers=headers
    )

    assert first.status_code == repeated.status_code == 200
    assert first.json()["revoked_at"] == repeated.json()["revoked_at"]
    for response in (restored, repeated_restore):
        assert response.status_code == 200
        assert response.json()["revoked_at"] is None
        assert response.json()["display_name"] == provisioned_agent.display_name
        assert response.json()["target_subnet"] == "192.168.1.0/24"


@pytest.mark.parametrize("action", ["revoke", "restore"])
def test_viewer_cannot_revoke_or_restore(
    action: str,
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.post(
        _path(provisioned_agent.id, action),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 403


@pytest.mark.parametrize("action", ["revoke", "restore"])
def test_unknown_and_foreign_agents_return_identical_404(
    action: str,
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    foreign = _other_org_agent(administrative_session)
    headers = bearer_headers(seeded_org.id, "admin")

    unknown = client.post(_path(uuid4(), action), headers=headers)
    other_org = client.post(_path(foreign.id, action), headers=headers)

    assert unknown.status_code == other_org.status_code == 404
    assert unknown.json() == other_org.json()
    administrative_session.refresh(foreign)
    assert foreign.revoked_at is None
