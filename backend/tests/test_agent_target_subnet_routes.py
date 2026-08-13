from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org
from api.schemas.agent_frames import AvailableSubnet
from api.services import agent_connections
from fastapi.testclient import TestClient
from sqlmodel import Session

AGENTS_PATH = "/api/v1/agents"
T0 = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)
ETH = "10.0.0.0/24"
WIFI = "192.168.1.0/24"
UNREPORTED = "172.16.0.0/24"
REPORTED_SUBNETS = [
    {"interface": "eth0", "cidr": ETH, "is_default_route": False},
    {"interface": "wlan0", "cidr": WIFI, "is_default_route": True},
]


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _path(agent_id) -> str:
    return f"{AGENTS_PATH}/{agent_id}"


def _register(agent_id, socket) -> None:
    asyncio.run(agent_connections.register(agent_id, socket, now=T0))


def _register_with_hello(agent_id, socket) -> None:
    reported = [AvailableSubnet(**entry) for entry in REPORTED_SUBNETS]

    async def _run() -> None:
        await agent_connections.register(agent_id, socket, now=T0)
        await agent_connections.set_hello(
            agent_id,
            socket,
            agent_version="0.2.0",
            available_subnets=reported,
            now=T0,
        )

    asyncio.run(_run())


def _stored(session: Session, agent_id) -> str | None:
    session.expire_all()
    return session.get(Agent, agent_id).target_subnet


def _seed_other_org_agent(session: Session, *, target_subnet: str | None) -> Agent:
    org = Org(name=f"other-{uuid4()}")
    session.add(org)
    session.flush()
    agent = Agent(
        org_id=org.id,
        display_name="Other Agent",
        public_key=b"\x03" * 32,
        target_subnet=target_subnet,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def test_choosing_a_reported_subnet_returns_detail_and_is_readable(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())
    headers = bearer_headers(seeded_org.id, "admin")

    response = client.patch(
        _path(provisioned_agent.id),
        json={"target_subnet": WIFI},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "agent_id",
        "display_name",
        "online",
        "last_seen_at",
        "available_subnets",
        "target_subnet",
        "active_command_id",
    }
    assert body["target_subnet"] == WIFI
    assert body["available_subnets"] == REPORTED_SUBNETS
    assert body["online"] is True

    listed = client.get(AGENTS_PATH, headers=headers).json()["data"]
    assert listed[0]["target_subnet"] == WIFI
    detail = client.get(_path(provisioned_agent.id), headers=headers).json()
    assert detail["target_subnet"] == WIFI


def test_re_choosing_replaces_the_stored_value(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())
    headers = bearer_headers(seeded_org.id, "admin")

    client.patch(
        _path(provisioned_agent.id), json={"target_subnet": WIFI}, headers=headers
    )
    response = client.patch(
        _path(provisioned_agent.id), json={"target_subnet": ETH}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["target_subnet"] == ETH
    assert _stored(administrative_session, provisioned_agent.id) == ETH


def test_unreported_subnet_is_refused_with_422(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())

    response = client.patch(
        _path(provisioned_agent.id),
        json={"target_subnet": UNREPORTED},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "subnet_not_reported"
    assert _stored(administrative_session, provisioned_agent.id) is None


@pytest.mark.parametrize("connected", [False, True])
def test_choosing_without_a_report_is_refused_with_409(
    connected: bool,
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    if connected:
        _register(provisioned_agent.id, AsyncMock())

    response = client.patch(
        _path(provisioned_agent.id),
        json={"target_subnet": WIFI},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "device_offline"
    assert _stored(administrative_session, provisioned_agent.id) is None


def test_viewer_may_not_choose(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())

    response = client.patch(
        _path(provisioned_agent.id),
        json={"target_subnet": WIFI},
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 403
    assert _stored(administrative_session, provisioned_agent.id) is None


def test_cross_org_choose_returns_404_and_leaves_the_other_org_untouched(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    foreign = _seed_other_org_agent(administrative_session, target_subnet=ETH)
    _register_with_hello(foreign.id, AsyncMock())

    response = client.patch(
        _path(foreign.id),
        json={"target_subnet": WIFI},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 404
    assert _stored(administrative_session, foreign.id) == ETH


def test_unknown_agent_returns_404(
    client: TestClient,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.patch(
        _path(uuid4()),
        json={"target_subnet": WIFI},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"target_subnet": WIFI, "unexpected": "x"},
        {"target_subnet": "not-a-cidr"},
    ],
)
def test_malformed_bodies_are_validation_errors(
    payload: dict,
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())

    response = client.patch(
        _path(provisioned_agent.id),
        json=payload,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert _stored(administrative_session, provisioned_agent.id) is None
