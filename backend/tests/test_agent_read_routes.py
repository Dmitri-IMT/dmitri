from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AvailableSubnet
from api.services import agent_connections
from conftest import ws_upgrade_headers
from fastapi.testclient import TestClient
from sqlmodel import Session

AGENTS_PATH = "/api/v1/agents"
T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
PERSISTED_LAST_SEEN = T0 - timedelta(hours=3)
REPORTED_SUBNETS = [
    {"interface": "eth0", "cidr": "10.0.0.0/24", "is_default_route": False},
    {"interface": "wlan0", "cidr": "192.168.1.0/24", "is_default_route": True},
]
SUMMARY_KEYS = {
    "agent_id",
    "display_name",
    "online",
    "last_seen_at",
    "revoked_at",
    "target_subnet",
    "active_command_id",
}


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_command(session: Session, *, org_id, agent_id, status: str) -> Command:
    scan_id = uuid4()
    session.add(
        ScanRecord(
            scan_id=scan_id,
            org_id=org_id,
            timestamp=datetime.now(timezone.utc),
            subnet="192.168.1.0/24",
            scan_mode="standard",
        )
    )
    session.flush()
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode="standard",
        subnet="192.168.1.0/24",
        status=status,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _seed_other_org_agent(session: Session) -> Agent:
    org = Org(name=f"other-{uuid4()}")
    session.add(org)
    session.flush()
    agent = Agent(
        org_id=org.id,
        display_name="Other Agent",
        public_key=b"\x02" * 32,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def test_list_agents_returns_org_rows_with_exact_keys(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert set(rows[0]) == SUMMARY_KEYS
    assert rows[0]["agent_id"] == str(provisioned_agent.id)
    assert rows[0]["display_name"] == provisioned_agent.display_name
    assert rows[0]["online"] is False
    assert rows[0]["revoked_at"] is None
    assert rows[0]["target_subnet"] is None


def test_list_and_detail_surface_revocation_time(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.revoked_at = T0
    administrative_session.add(provisioned_agent)
    administrative_session.commit()
    headers = bearer_headers(seeded_org.id, "admin")

    listed = client.get(AGENTS_PATH, headers=headers).json()["data"][0]
    detail = client.get(_detail_path(provisioned_agent.id), headers=headers).json()

    assert datetime.fromisoformat(listed["revoked_at"]) == T0
    assert detail["revoked_at"] == listed["revoked_at"]


def test_list_agents_excludes_other_orgs(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    foreign = _seed_other_org_agent(administrative_session)

    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 200
    ids = [row["agent_id"] for row in response.json()["data"]]
    assert ids == [str(provisioned_agent.id)]
    assert str(foreign.id) not in ids


def test_list_agents_allows_viewer(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "viewer")
    )

    assert response.status_code == 200


def test_list_agents_surfaces_active_command_and_ignores_terminal(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    done = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="done",
    )

    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "admin")
    )
    assert response.json()["data"][0]["active_command_id"] is None

    queued = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
    )

    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "admin")
    )
    active = response.json()["data"][0]["active_command_id"]
    assert active == str(queued.id)
    assert active != str(done.id)


def test_list_agents_empty_org_returns_empty_data(
    client: TestClient,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.get(
        AGENTS_PATH, headers=bearer_headers(seeded_org.id, "admin")
    )

    assert response.status_code == 200
    assert response.json() == {"data": []}


def _detail_path(agent_id) -> str:
    return f"{AGENTS_PATH}/{agent_id}"


def _hello_payload() -> str:
    return json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": REPORTED_SUBNETS,
        }
    )


def _sync(ws) -> None:
    ws.send_text("not json")
    assert ws.receive_json() == {"type": "error", "message": "invalid JSON"}


def _register_with_hello(agent_id, socket, *, subnets=None) -> None:
    reported = [
        AvailableSubnet(**entry)
        for entry in (REPORTED_SUBNETS if subnets is None else subnets)
    ]

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


def test_detail_reports_both_subnets_in_order(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id, AsyncMock())

    response = client.get(
        _detail_path(provisioned_agent.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == SUMMARY_KEYS | {"available_subnets"}
    assert body["available_subnets"] == REPORTED_SUBNETS
    assert body["online"] is True
    assert body["target_subnet"] is None


def test_detail_never_connected_reports_nothing(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.get(
        _detail_path(provisioned_agent.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["available_subnets"] == []
    assert body["last_seen_at"] is None
    assert body["online"] is False


def test_detail_online_flips_and_falls_back_to_persisted_last_seen(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.last_seen_at = PERSISTED_LAST_SEEN
    administrative_session.add(provisioned_agent)
    administrative_session.commit()
    socket = AsyncMock()
    _register_with_hello(provisioned_agent.id, socket)
    headers = bearer_headers(seeded_org.id, "admin")

    connected = client.get(_detail_path(provisioned_agent.id), headers=headers)
    assert connected.json()["online"] is True

    asyncio.run(
        agent_connections.unregister(provisioned_agent.id, socket, now=T0)
    )

    offline = client.get(_detail_path(provisioned_agent.id), headers=headers)
    body = offline.json()
    assert body["online"] is False
    assert body["available_subnets"] == []
    assert datetime.fromisoformat(body["last_seen_at"]) == PERSISTED_LAST_SEEN


def test_reported_subnets_are_never_stored_across_a_real_socket(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
    agent_keypair,
) -> None:
    private_key, _public_key = agent_keypair
    path = f"{_detail_path(provisioned_agent.id)}/commands"
    headers = bearer_headers(seeded_org.id, "admin")

    with client.websocket_connect(
        path, headers=ws_upgrade_headers(private_key, provisioned_agent.id)
    ) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)
        connected = client.get(_detail_path(provisioned_agent.id), headers=headers)
        assert connected.json()["online"] is True
        assert connected.json()["available_subnets"] == REPORTED_SUBNETS

    offline = client.get(_detail_path(provisioned_agent.id), headers=headers)
    assert offline.json()["online"] is False
    assert offline.json()["available_subnets"] == []

    administrative_session.expire_all()
    row = administrative_session.get(Agent, provisioned_agent.id)
    assert row.target_subnet is None
    assert not hasattr(row, "available_subnets")


def test_detail_unknown_and_foreign_agent_return_identical_404(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    foreign = _seed_other_org_agent(administrative_session)
    headers = bearer_headers(seeded_org.id, "admin")

    unknown = client.get(_detail_path(uuid4()), headers=headers)
    other_org = client.get(_detail_path(foreign.id), headers=headers)

    assert unknown.status_code == 404
    assert other_org.status_code == 404
    assert unknown.json() == other_org.json()


def test_detail_allows_viewer_and_surfaces_active_command(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    headers = bearer_headers(seeded_org.id, "viewer")
    _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="done",
    )

    response = client.get(_detail_path(provisioned_agent.id), headers=headers)
    assert response.status_code == 200
    assert response.json()["active_command_id"] is None

    queued = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
    )

    response = client.get(_detail_path(provisioned_agent.id), headers=headers)
    assert response.status_code == 200
    assert response.json()["active_command_id"] == str(queued.id)
