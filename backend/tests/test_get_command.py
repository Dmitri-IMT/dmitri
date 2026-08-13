from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _command_path(command_id) -> str:
    return f"/api/v1/commands/{command_id}"


def _seed_command(
    session: Session,
    *,
    org_id,
    agent_id,
    status: str,
    scan_id=None,
    error_code: str | None = None,
) -> Command:
    if scan_id is not None:
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
        error_code=error_code,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def _seed_other_org_command(session: Session) -> Command:
    org = Org(name=f"other-{uuid4()}")
    session.add(org)
    session.flush()
    agent = Agent(
        org_id=org.id,
        display_name="Other Agent",
        public_key=b"\x02" * 32,
    )
    session.add(agent)
    session.flush()
    return _seed_command(
        session,
        org_id=org.id,
        agent_id=agent.id,
        status="delivered",
        scan_id=uuid4(),
    )


def test_get_command_returns_200_for_own_org(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    scan_id = uuid4()
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="delivered",
        scan_id=scan_id,
    )

    response = client.get(
        _command_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["command_id"] == str(command.id)
    assert body["scan_id"] == str(scan_id)
    assert body["agent_id"] == str(provisioned_agent.id)
    assert body["status"] == "delivered"
    assert body["scan_mode"] == "standard"
    assert body["subnet"] == "192.168.1.0/24"
    assert "created_at" in body


def test_get_command_unknown_id_returns_404(
    client: TestClient,
    seeded_org: Org,
    bearer_headers,
) -> None:
    response = client.get(
        _command_path(uuid4()),
        headers=bearer_headers(seeded_org.id, "admin"),
    )
    assert response.status_code == 404


def test_get_command_cross_org_returns_404(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    bearer_headers,
) -> None:
    foreign_command = _seed_other_org_command(administrative_session)

    response = client.get(
        _command_path(foreign_command.id),
        headers=bearer_headers(seeded_org.id, "admin"),
    )

    assert response.status_code == 404
    assert response.status_code != 403


def test_get_command_expired_serialises_null_scan_id(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="expired",
        scan_id=None,
    )

    response = client.get(
        _command_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "expired"
    assert body["scan_id"] is None


def test_get_command_does_not_mutate_status(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="delivered",
        scan_id=uuid4(),
    )
    headers = bearer_headers(seeded_org.id, "viewer")

    first = client.get(_command_path(command.id), headers=headers)
    second = client.get(_command_path(command.id), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "delivered"
    assert second.json()["status"] == "delivered"
    administrative_session.refresh(command)
    assert command.status == "delivered"


def test_get_command_off_contract_error_code_returns_unknown_not_500(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="failed",
        scan_id=uuid4(),
        error_code="scan_timeout",
    )

    response = client.get(
        _command_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    assert response.status_code != 500
    assert response.json()["error_code"] == "unknown"


def test_get_command_published_error_code_round_trips(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="failed",
        scan_id=uuid4(),
        error_code="scan_failed",
    )

    response = client.get(
        _command_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["error_code"] == "scan_failed"


def test_get_command_queued_returns_null_error_code(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    bearer_headers,
) -> None:
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
    )

    response = client.get(
        _command_path(command.id),
        headers=bearer_headers(seeded_org.id, "viewer"),
    )

    assert response.status_code == 200
    assert response.json()["error_code"] is None
