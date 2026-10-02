"""Remote cancel over the agent command channel (spec 049)."""

from __future__ import annotations

from uuid import UUID

import pytest
from api.db.session import get_session
from api.dependencies.agent_auth import AgentIdentity
from api.main import app
from api.models.activity import ActivityRecord
from api.models.command import Agent
from api.models.identity import Org
from api.schemas import HostPayload, PortPayload, ScanIngestRequest
from api.services import commands
from api.services.persistence import ingest_scan
from conftest import ws_upgrade_headers
from sqlmodel import Session, select
from starlette.testclient import TestClient
from test_agent_ws_channel import (
    COMMAND_ID,
    T0,
    _hello_payload,
    _seed_command,
    _seed_scan,
    _status_payload,
    _sync,
    _ws_path,
)


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def _cancel_path(command_id: UUID) -> str:
    return f"/api/v1/commands/{command_id}/cancel"


def _partial_user_cancel_ingest(
    scan_id: UUID,
) -> ScanIngestRequest:
    return ScanIngestRequest(
        scan_id=scan_id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        hosts=[
            HostPayload(
                ip="10.0.0.5",
                mac=None,
                hostname="host-a",
                vendor="vendor",
                ports=[
                    PortPayload(
                        port=22, protocol="tcp", state="open", service="ssh"
                    )
                ],
            )
        ],
        findings=[],
        metadata={"terminated_by": "user_cancel"},
    )


def test_hello_sends_only_eligible_cancel_frames(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    eligible_scan = _seed_scan(administrative_session, seeded_org.id)
    eligible_scan.status = "cancelled"
    administrative_session.add(eligible_scan)
    administrative_session.commit()
    eligible = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="cancelled",
        scan_id=eligible_scan.scan_id,
    )

    running_scan = _seed_scan(administrative_session, seeded_org.id)
    running_scan.status = "accepted"
    administrative_session.add(running_scan)
    administrative_session.commit()
    running = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=running_scan.scan_id,
        command_id=COMMAND_ID,
    )
    running.delivered_at = T0
    running.started_at = T0
    administrative_session.add(running)
    administrative_session.commit()
    administrative_session.refresh(running)
    started_before = running.started_at
    delivered_before = running.delivered_at

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        assert ws.receive_json() == {"type": "cancel", "command_id": str(eligible.id)}
        ws.send_text(_status_payload(command_id=running.id, status="running"))
        _sync(ws)
        ws.send_text(_status_payload(command_id=running.id, status="uploading"))
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(running)
    assert running.status == "uploading"
    assert running.started_at == started_before
    assert running.delivered_at == delivered_before


def test_late_upload_accepted_after_cancel_catch_up(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    cancelled_scan = _seed_scan(administrative_session, seeded_org.id)
    cancelled_scan.status = "cancelled"
    administrative_session.add(cancelled_scan)
    administrative_session.commit()
    cancelled = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="cancelled",
        scan_id=cancelled_scan.scan_id,
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        assert ws.receive_json() == {
            "type": "cancel",
            "command_id": str(cancelled.id),
        }
        _sync(ws)

    ingest_scan(
        administrative_session,
        _partial_user_cancel_ingest(cancelled_scan.scan_id),
        identity=AgentIdentity(
            agent_id=provisioned_agent.id, org_id=seeded_org.id
        ),
        now=T0,
    )

    administrative_session.expire_all()
    administrative_session.refresh(cancelled)
    administrative_session.refresh(cancelled_scan)
    assert cancelled.status == "cancelled"
    assert cancelled_scan.status == "completed"


def test_connected_cancel_partial_ingest_and_device_free(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
    bearer_headers,
):
    private_key, _public_key = agent_keypair
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)

        response = client.post(
            _cancel_path(command.id),
            headers=bearer_headers(seeded_org.id, "admin"),
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"
        assert ws.receive_json() == {
            "type": "cancel",
            "command_id": str(command.id),
        }

        ws.send_text(_status_payload(command_id=command.id, status="uploading"))
        _sync(ws)

        ingest_scan(
            administrative_session,
            _partial_user_cancel_ingest(scan.scan_id),
            identity=AgentIdentity(
                agent_id=provisioned_agent.id, org_id=seeded_org.id
            ),
            now=T0,
        )

        ws.send_text(_status_payload(command_id=command.id, status="cancelled"))
        _sync(ws)

        administrative_session.expire_all()
        administrative_session.refresh(command)
        administrative_session.refresh(scan)
        assert command.status == "cancelled"
        assert scan.status == "completed"
        activities = administrative_session.exec(
            select(ActivityRecord).where(
                ActivityRecord.org_id == seeded_org.id,
                ActivityRecord.subject_id == scan.scan_id,
            )
        ).all()
        assert [row.kind for row in activities] == ["scan_cancelled"]
        assert (
            commands.active_command_for(
                administrative_session, provisioned_agent.id
            )
            is None
        )

        enqueue = client.post(
            f"/api/v1/agents/{provisioned_agent.id}/commands",
            json={"scan_mode": "standard", "subnet": "192.168.1.0/24"},
            headers=bearer_headers(seeded_org.id, "admin"),
        )
        assert enqueue.status_code == 201
        delivered = ws.receive_json()
        assert delivered["type"] == "command"
        assert delivered["command_id"] == enqueue.json()["command_id"]


def test_connected_cancel_race_ends_done_without_cancelled(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
    bearer_headers,
):
    private_key, _public_key = agent_keypair
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)

        response = client.post(
            _cancel_path(command.id),
            headers=bearer_headers(seeded_org.id, "admin"),
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"
        assert ws.receive_json() == {
            "type": "cancel",
            "command_id": str(command.id),
        }

        administrative_session.refresh(command)
        assert command.status == "running"

        ws.send_text(_status_payload(command_id=command.id, status="uploading"))
        _sync(ws)

        ingest_scan(
            administrative_session,
            _partial_user_cancel_ingest(scan.scan_id).model_copy(
                update={"metadata": None}
            ),
            identity=AgentIdentity(
                agent_id=provisioned_agent.id, org_id=seeded_org.id
            ),
            now=T0,
        )

        ws.send_text(_status_payload(command_id=command.id, status="done"))
        _sync(ws)

        administrative_session.expire_all()
        administrative_session.refresh(command)
        administrative_session.refresh(scan)
        assert command.status == "done"
        assert scan.status == "completed"
        activities = administrative_session.exec(
            select(ActivityRecord).where(
                ActivityRecord.org_id == seeded_org.id,
                ActivityRecord.subject_id == scan.scan_id,
            )
        ).all()
        assert [row.kind for row in activities] == ["scan_finished"]
        assert (
            commands.active_command_for(
                administrative_session, provisioned_agent.id
            )
            is None
        )

        enqueue = client.post(
            f"/api/v1/agents/{provisioned_agent.id}/commands",
            json={"scan_mode": "standard", "subnet": "192.168.1.0/24"},
            headers=bearer_headers(seeded_org.id, "admin"),
        )
        assert enqueue.status_code == 201
        delivered = ws.receive_json()
        assert delivered["type"] == "command"
        assert delivered["command_id"] == enqueue.json()["command_id"]


def test_offline_cancel_reconnect_late_ingest_and_device_free(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
    bearer_headers,
):
    private_key, _public_key = agent_keypair
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

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        assert ws.receive_json() == {
            "type": "cancel",
            "command_id": str(command.id),
        }
        _sync(ws)

        ingest_scan(
            administrative_session,
            _partial_user_cancel_ingest(scan.scan_id),
            identity=AgentIdentity(
                agent_id=provisioned_agent.id, org_id=seeded_org.id
            ),
            now=T0,
        )

        administrative_session.expire_all()
        administrative_session.refresh(command)
        administrative_session.refresh(scan)
        assert command.status == "cancelled"
        assert scan.status == "completed"
        activities = administrative_session.exec(
            select(ActivityRecord).where(
                ActivityRecord.org_id == seeded_org.id,
                ActivityRecord.subject_id == scan.scan_id,
            )
        ).all()
        assert [row.kind for row in activities] == ["scan_cancelled"]
        assert (
            commands.active_command_for(
                administrative_session, provisioned_agent.id
            )
            is None
        )

        enqueue = client.post(
            f"/api/v1/agents/{provisioned_agent.id}/commands",
            json={"scan_mode": "standard", "subnet": "192.168.1.0/24"},
            headers=bearer_headers(seeded_org.id, "admin"),
        )
        assert enqueue.status_code == 201
        delivered = ws.receive_json()
        assert delivered["type"] == "command"
        assert delivered["command_id"] == enqueue.json()["command_id"]
