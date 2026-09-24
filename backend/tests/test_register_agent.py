from __future__ import annotations

from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org
from fastapi.testclient import TestClient
from sqlmodel import Session


def test_admin_registers_an_agent_in_their_org(
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agents",
            headers=bearer_headers(seeded_org.id, "admin"),
            json={
                "display_name": "Lab Pi 4",
                "public_key": "ab" * 32,
            },
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    agent_id = response.json()["agent_id"]
    stored = administrative_session.get(Agent, agent_id)
    assert stored is not None
    assert stored.org_id == seeded_org.id
    assert stored.display_name == "Lab Pi 4"
    assert stored.public_key == bytes.fromhex("ab" * 32)


def test_register_rejects_a_short_public_key(
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agents",
            headers=bearer_headers(seeded_org.id, "admin"),
            json={"display_name": "Lab Pi", "public_key": "abcd"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 422
