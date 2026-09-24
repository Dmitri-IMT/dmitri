from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org
from api.models.persistence import utc_now
from api.services.agents import register_agent
from fastapi.testclient import TestClient
from sqlmodel import Session, select


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


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": "Lab Pi", "public_key": "abcd"},
        {"display_name": "Lab Pi", "public_key": "zz" * 32},
        {"display_name": "", "public_key": "ab" * 32},
    ],
    ids=["short-key", "non-hex-key", "empty-name"],
)
def test_register_rejects_an_invalid_body(
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
    body: dict[str, str],
) -> None:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agents",
            headers=bearer_headers(seeded_org.id, "admin"),
            json=body,
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 422


def test_registration_retry_preserves_identity_and_revocation(
    client,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    headers = bearer_headers(seeded_org.id, "admin")
    body = {"display_name": "Lab Pi", "public_key": "ab" * 32}
    first = client.post("/api/v1/agents", headers=headers, json=body)
    agent = administrative_session.get(Agent, first.json()["agent_id"])
    agent.revoked_at = utc_now()
    administrative_session.add(agent)
    administrative_session.commit()
    revoked_at = agent.revoked_at

    retry = client.post(
        "/api/v1/agents",
        headers=headers,
        json={**body, "display_name": "Retry name"},
    )

    assert retry.status_code == 201
    assert retry.json() == first.json()
    administrative_session.refresh(agent)
    assert agent.display_name == "Lab Pi"
    assert agent.revoked_at == revoked_at
    assert len(administrative_session.exec(select(Agent)).all()) == 1


def test_concurrent_registration_retries_share_identity(
    administrative_session: Session,
    seeded_org: Org,
    migrated_database,
) -> None:
    org_id = seeded_org.id
    barrier = Barrier(2)

    def register_once():
        with Session(migrated_database) as session:
            org = session.get(Org, org_id)
            barrier.wait(timeout=5)
            agent = register_agent(
                session,
                org=org,
                display_name="Lab Pi",
                public_key=b"a" * 32,
            )
            return agent.id, org.ot_digest_key

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: register_once(), range(2)))

    assert results[0] == results[1]
    assert results[0][1] is not None
    assert len(administrative_session.exec(select(Agent)).all()) == 1


def test_registration_identity_is_scoped_to_org(
    administrative_session: Session,
    seeded_org: Org,
) -> None:
    other = Org(name="Other org")
    administrative_session.add(other)
    administrative_session.commit()
    first = register_agent(
        administrative_session,
        org=seeded_org,
        display_name="First Pi",
        public_key=b"a" * 32,
    )
    second = register_agent(
        administrative_session,
        org=other,
        display_name="Second Pi",
        public_key=b"a" * 32,
    )
    assert first.id != second.id
    assert first.org_id != second.org_id
