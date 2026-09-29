from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.activity import ActivityRecord
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.schemas.agent_frames import AgentCancelFrame, AvailableSubnet
from api.services import agent_connections, commands
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.websockets import WebSocketState

T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
STALE = T0 - timedelta(minutes=20)
REQUEST_BODY = {"scan_mode": "standard", "subnet": "192.168.1.0/24"}


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _commands_path(agent_id) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


def _cancel_path(command_id) -> str:
    return f"/api/v1/commands/{command_id}/cancel"


def _seed_command(
    session: Session,
    *,
    org_id,
    agent_id,
    status: str,
    scan_id=None,
    scan_mode: str = "standard",
    created_at: datetime | None = None,
    delivered_at: datetime | None = None,
) -> Command:
    command = Command(
        org_id=org_id,
        agent_id=agent_id,
        scan_id=scan_id,
        scan_mode=scan_mode,
        subnet="192.168.1.0/24",
        status=status,
        delivered_at=delivered_at,
    )
    if created_at is not None:
        command.created_at = created_at
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _seed_scan(session: Session, org_id) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


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


def test_enqueue_returns_201_with_command_summary(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"command_id", "scan_id", "agent_id", "status"}
    assert body["agent_id"] == str(provisioned_agent.id)
    assert body["status"] == "delivered"
    command = administrative_session.get(Command, body["command_id"])
    assert command is not None
    assert str(command.scan_id) == body["scan_id"]
    assert administrative_session.get(ScanRecord, command.scan_id) is not None


def test_enqueue_persists_nspi_submode(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())
    response = client.post(
        _commands_path(provisioned_agent.id),
        json={
            "scan_mode": "nspi",
            "subnet": "192.168.1.0/24",
            "nspi_options": {"version": 1, "submode": "read_only_mapping"},
        },
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    command = administrative_session.get(Command, response.json()["command_id"])
    assert command is not None
    assert command.nspi_options == {
        "version": 1,
        "submode": "read_only_mapping",
        "active_risk_acknowledged": False,
        "change_ticket": None,
    }


def test_enqueue_rejects_nspi_options_for_general_scan(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.post(
        _commands_path(provisioned_agent.id),
        json={
            "scan_mode": "quick",
            "subnet": "192.168.1.0/24",
            "nspi_options": {"version": 1, "submode": "inventory"},
        },
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422


def test_viewer_cannot_enqueue_command(
    client: TestClient, provisioned_agent: Agent, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 403


def test_unknown_agent_returns_403(
    client: TestClient, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        _commands_path(uuid4()),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 403


def test_cross_org_agent_returns_403(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    other_agent = _seed_other_org_agent(administrative_session)

    response = client.post(
        _commands_path(other_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 403


def test_viewer_cannot_cancel_command(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 403


def test_other_org_command_is_not_found_for_cancel(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    other_agent = _seed_other_org_agent(administrative_session)
    scan = _seed_scan(administrative_session, other_agent.org_id)
    command = _seed_command(
        administrative_session,
        org_id=other_agent.org_id,
        agent_id=other_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 404


def test_online_cancel_returns_202_and_sends_one_frame(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "running"
    assert ws.send_text.await_count == 1
    frame = AgentCancelFrame.model_validate_json(ws.send_text.await_args.args[0])
    assert frame.command_id == command.id


def test_offline_cancel_retires_scan_and_frees_agent(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "cancelled"
    assert scan.status == "cancelled"
    activities = administrative_session.exec(
        select(ActivityRecord).where(
            ActivityRecord.org_id == seeded_org.id,
            ActivityRecord.subject_id == scan.scan_id,
        )
    ).all()
    assert [activity.kind for activity in activities] == ["scan_cancelled"]
    active = commands.active_command_for(administrative_session, provisioned_agent.id)
    assert active is None


def test_uploading_command_cannot_be_cancelled(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="uploading",
        scan_id=scan.scan_id,
    )

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "command_not_cancellable"


def test_terminal_cancel_is_idempotent_and_sends_no_frame(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="cancelled",
        scan_id=scan.scan_id,
    )
    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _cancel_path(command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    ws.send_text.assert_not_awaited()


def test_device_busy_from_active_command(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "device_busy",
            "message": "That Pi is already scanning.",
            "details": {},
        }
    }


def test_device_busy_from_integrity_error_matches_read_side_body(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    read_side = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )
    assert read_side.status_code == 409

    def _raise_integrity_error(*args, **kwargs):
        raise IntegrityError("insert", {}, Exception("duplicate active command"))

    monkeypatch.setattr(commands, "active_command_for", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "enqueue", _raise_integrity_error)

    integrity_side = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert integrity_side.status_code == 409
    assert integrity_side.content == read_side.content


def test_device_offline_expires_command_without_scan(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "device_offline",
            "message": "Pi seems to be offline.",
            "details": {},
        }
    }
    command = administrative_session.exec(select(Command)).one()
    assert command.status == "expired"
    assert command.scan_id is None
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_revoked_agent_with_live_socket_returns_503_without_scan(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.revoked_at = T0
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    ws = AsyncMock()
    ws.application_state = WebSocketState.CONNECTED

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "device_offline"
    ws.send_text.assert_not_awaited()
    command = administrative_session.exec(select(Command)).one()
    assert command.status == "expired"
    assert command.scan_id is None
    assert administrative_session.exec(select(ScanRecord)).all() == []


def test_enqueue_sweep_clears_stale_command_wedge(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.last_seen_at = STALE.replace(tzinfo=None)
    provisioned_agent.connected_at = None
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    scan = _seed_scan(administrative_session, seeded_org.id)
    stale = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    assert commands.active_command_for(administrative_session, provisioned_agent.id)

    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    administrative_session.refresh(stale)
    assert stale.status == "failed"
    assert response.json()["status"] == "delivered"


def test_enqueue_sweep_clears_overdue_connected_command_wedge(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.last_seen_at = T0.replace(tzinfo=None)
    provisioned_agent.connected_at = T0.replace(tzinfo=None)
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    scan = _seed_scan(administrative_session, seeded_org.id)
    stale = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
        scan_mode="quick",
        delivered_at=T0 - timedelta(seconds=10801),
    )

    ws = AsyncMock()

    async def register() -> None:
        await agent_connections.register(provisioned_agent.id, ws, now=T0)

    asyncio.run(register())

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    administrative_session.refresh(stale)
    assert stale.status == "failed"
    assert stale.error_code == "scan_timeout"
    assert response.json()["status"] == "delivered"


UNREPORTED = "10.9.9.0/24"
REPORTED = [
    AvailableSubnet(interface="eth0", cidr="192.168.1.0/24", is_default_route=True),
]


def _register_with_hello(agent_id) -> None:
    ws = AsyncMock()

    async def _run() -> None:
        await agent_connections.register(agent_id, ws, now=T0)
        await agent_connections.set_hello(
            agent_id,
            ws,
            agent_version="0.2.0",
            available_subnets=REPORTED,
            now=T0,
        )

    asyncio.run(_run())


def test_reported_subnet_is_delivered(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id)

    response = client.post(
        _commands_path(provisioned_agent.id),
        json=REQUEST_BODY,
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "delivered"


def test_unreported_subnet_returns_422_without_command_row(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    _register_with_hello(provisioned_agent.id)

    response = client.post(
        _commands_path(provisioned_agent.id),
        json={"scan_mode": "standard", "subnet": UNREPORTED},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "subnet_not_reported"
    assert administrative_session.exec(select(Command)).all() == []


def test_stale_stored_choice_is_refused_and_left_alone(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    provisioned_agent.target_subnet = UNREPORTED
    administrative_session.add(provisioned_agent)
    administrative_session.commit()
    _register_with_hello(provisioned_agent.id)

    response = client.post(
        _commands_path(provisioned_agent.id),
        json={"scan_mode": "standard", "subnet": UNREPORTED},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422
    administrative_session.expire_all()
    stored = administrative_session.get(Agent, provisioned_agent.id)
    assert stored.target_subnet == UNREPORTED


def test_busy_agent_wins_over_unreported_subnet(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan = _seed_scan(administrative_session, seeded_org.id)
    _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    _register_with_hello(provisioned_agent.id)

    response = client.post(
        _commands_path(provisioned_agent.id),
        json={"scan_mode": "standard", "subnet": UNREPORTED},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "device_busy"


def test_missing_subnet_key_is_rejected_by_the_request_schema(
    client: TestClient,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.post(
        _commands_path(provisioned_agent.id),
        json={"scan_mode": "standard"},
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] != "subnet_not_reported"
