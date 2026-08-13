from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.services import agent_connections, device_sig
from conftest import ws_upgrade_headers
from sqlmodel import Session
from starlette.testclient import TestClient, WebSocketTestSession

COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")
T0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)


def _ws_path(agent_id: UUID) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


DEFAULT_SUBNETS = [
    {"interface": "eth0", "cidr": "10.0.0.0/24", "is_default_route": False},
    {"interface": "wlan0", "cidr": "192.168.1.0/24", "is_default_route": True},
]


def _hello_payload(*, available_subnets: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": (
                DEFAULT_SUBNETS if available_subnets is None else available_subnets
            ),
        }
    )


def _status_payload(
    *,
    command_id: UUID = COMMAND_ID,
    status: str = "running",
    error_code: str | None = None,
) -> str:
    payload: dict = {
        "type": "status",
        "command_id": str(command_id),
        "status": status,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    return json.dumps(payload)


def _sync(ws: WebSocketTestSession) -> None:
    """Block until the server has drained every frame sent before this call.

    The handler processes frames sequentially in a single loop, so a reply to
    this sentinel proves the preceding frame was already handled. "not json"
    touches neither the registry nor the DB, so it is safe to use anywhere.
    """
    ws.send_text("not json")
    assert ws.receive_json() == {"type": "error", "message": "invalid JSON"}


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


def _seed_command(
    session: Session,
    *,
    org_id,
    agent_id,
    status: str,
    scan_id=None,
    command_id: UUID | None = None,
) -> Command:
    command = Command(
        id=command_id or uuid4(),
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


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_disconnect_marks_agent_offline_without_bumping_last_seen(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    path = _ws_path(provisioned_agent.id)

    with client.websocket_connect(path, headers=headers) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)
        assert agent_connections.get_hello(provisioned_agent.id) is not None
        last_seen_after_hello = agent_connections.last_seen_at(provisioned_agent.id)

    assert not agent_connections.is_online(provisioned_agent.id)
    administrative_session.expire(provisioned_agent)
    assert (
        administrative_session.get(Agent, provisioned_agent.id).last_seen_at
        == last_seen_after_hello
    )


def test_hello_frame_cached_in_registry_and_bumps_last_seen(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    path = _ws_path(provisioned_agent.id)
    initial_last_seen = provisioned_agent.last_seen_at

    with client.websocket_connect(path, headers=headers) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)

        hello = agent_connections.get_hello(provisioned_agent.id)
        assert hello is not None
        assert hello[0] == "0.2.0"
        assert [
            (s.interface, s.cidr, s.is_default_route) for s in hello[1]
        ] == [
            ("eth0", "10.0.0.0/24", False),
            ("wlan0", "192.168.1.0/24", True),
        ]

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at is not None
    if initial_last_seen is not None:
        assert provisioned_agent.last_seen_at > initial_last_seen


def test_reconnect_replaces_old_socket_without_stale_unregister(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    path = _ws_path(provisioned_agent.id)
    agent_id = provisioned_agent.id

    with client.websocket_connect(
        path, headers=ws_upgrade_headers(private_key, agent_id)
    ) as ws_a:
        assert agent_connections.is_online(agent_id)
        socket_before_b = agent_connections.get_socket(agent_id)
        assert socket_before_b is not None

        with client.websocket_connect(
            path, headers=ws_upgrade_headers(private_key, agent_id)
        ) as ws_b:
            assert agent_connections.is_online(agent_id)
            socket_after_b = agent_connections.get_socket(agent_id)
            assert socket_after_b is not None
            assert agent_connections.get_socket(agent_id) is socket_after_b

            ws_b.send_text(_hello_payload())

            close_msg = ws_a.receive()
            assert close_msg == {
                "type": "websocket.close",
                "code": 4000,
                "reason": "replaced",
            }
            _sync(ws_b)

            hello = agent_connections.get_hello(agent_id)
            assert hello is not None
            assert hello[0] == "0.2.0"

        assert not agent_connections.is_online(agent_id)

    assert not agent_connections.is_online(agent_id)


def test_reconnect_replaces_available_subnets_instead_of_merging(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    path = _ws_path(provisioned_agent.id)
    agent_id = provisioned_agent.id
    reconnect_subnets = [
        {"interface": "eth1", "cidr": "172.16.0.0/24", "is_default_route": True},
    ]

    with client.websocket_connect(
        path, headers=ws_upgrade_headers(private_key, agent_id)
    ) as ws_a:
        ws_a.send_text(_hello_payload())
        _sync(ws_a)
        assert len(agent_connections.get_hello(agent_id)[1]) == 2

    with client.websocket_connect(
        path, headers=ws_upgrade_headers(private_key, agent_id)
    ) as ws_b:
        ws_b.send_text(_hello_payload(available_subnets=reconnect_subnets))
        _sync(ws_b)

        hello = agent_connections.get_hello(agent_id)
        assert hello is not None
        assert [(s.interface, s.cidr, s.is_default_route) for s in hello[1]] == [
            ("eth1", "172.16.0.0/24", True),
        ]


@pytest.mark.parametrize(
    "bad_frame",
    [
        "not json",
        json.dumps(
            {
                "type": "hello",
                "agent_version": "0.2.0",
                "available_subnets": [
                    {"interface": "eth0", "cidr": "10.0.0.0/24"},
                ],
            }
        ),
        json.dumps({"type": "nope"}),
        json.dumps(
            {
                "type": "status",
                "command_id": str(COMMAND_ID),
                "status": "queued",
            }
        ),
    ],
)
def test_malformed_frames_send_error_and_keep_socket_usable(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
    bad_frame: str,
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    path = _ws_path(provisioned_agent.id)

    with client.websocket_connect(path, headers=headers) as ws:
        ws.send_text(bad_frame)
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["message"]

        ws.send_text(_hello_payload())
        _sync(ws)
        hello = agent_connections.get_hello(provisioned_agent.id)
        assert hello is not None
        assert hello[0] == "0.2.0"


def test_two_agents_isolated_on_malformed_frame(
    client: TestClient,
    administrative_session: Session,
    seeded_org: Org,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key_a, _ = agent_keypair
    private_key_b, public_key_b = device_sig.generate_keypair()
    agent_b = Agent(
        org_id=seeded_org.id, display_name="Agent B", public_key=public_key_b
    )
    administrative_session.add(agent_b)
    administrative_session.commit()
    administrative_session.refresh(agent_b)

    path_a = _ws_path(provisioned_agent.id)
    path_b = _ws_path(agent_b.id)

    with ExitStack() as stack:
        ws_a = stack.enter_context(
            client.websocket_connect(
                path_a, headers=ws_upgrade_headers(private_key_a, provisioned_agent.id)
            )
        )
        ws_b = stack.enter_context(
            client.websocket_connect(
                path_b, headers=ws_upgrade_headers(private_key_b, agent_b.id)
            )
        )
        assert agent_connections.is_online(provisioned_agent.id)
        assert agent_connections.is_online(agent_b.id)

        ws_a.send_text("not json")
        error = ws_a.receive_json()
        assert error["type"] == "error"

        assert agent_connections.is_online(agent_b.id)
        ws_b.send_text(_hello_payload())
        _sync(ws_b)
        assert agent_connections.get_hello(agent_b.id) is not None


def test_running_frame_on_queued_applies_and_backfills_delivered_at(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _ = agent_keypair
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="queued",
        scan_id=scan.scan_id,
    )
    assert command.delivered_at is None

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_status_payload(command_id=command.id, status="running"))
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "running"
    assert command.delivered_at is not None
    assert command.started_at is not None
    assert scan.status == "accepted"


def test_duplicate_running_frame_silently_ignored(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _ = agent_keypair
    scan = _seed_scan(administrative_session, seeded_org.id)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    administrative_session.refresh(command)
    status_before = command.status
    started_before = command.started_at
    delivered_before = command.delivered_at
    error_before = command.error_code
    scan_status_before = scan.status

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_status_payload(command_id=command.id, status="running"))
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == status_before
    assert command.started_at == started_before
    assert command.delivered_at == delivered_before
    assert command.error_code == error_before
    assert scan.status == scan_status_before


def test_unknown_command_id_sends_error_and_keeps_socket_open(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _ = agent_keypair

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_status_payload(command_id=uuid4(), status="running"))
        error = ws.receive_json()
        assert error == {"type": "error", "message": "unknown command_id"}

        ws.send_text(_hello_payload())
        _sync(ws)
        hello = agent_connections.get_hello(provisioned_agent.id)
        assert hello is not None
        assert hello[0] == "0.2.0"


def test_other_agents_command_id_treated_as_unknown(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key_a, _ = agent_keypair
    private_key_b, public_key_b = device_sig.generate_keypair()
    agent_b = Agent(
        org_id=seeded_org.id, display_name="Agent B", public_key=public_key_b
    )
    administrative_session.add(agent_b)
    administrative_session.commit()
    administrative_session.refresh(agent_b)

    scan = _seed_scan(administrative_session, seeded_org.id)
    other_command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=agent_b.id,
        status="queued",
        scan_id=scan.scan_id,
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key_a, provisioned_agent.id),
    ) as ws:
        ws.send_text(_status_payload(command_id=other_command.id, status="running"))
        error = ws.receive_json()
        assert error == {"type": "error", "message": "unknown command_id"}
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(other_command)
    administrative_session.refresh(scan)
    assert other_command.status == "queued"
    assert other_command.delivered_at is None
    assert other_command.started_at is None
    assert scan.status == "pending"


def test_failed_frame_persists_error_code(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _ = agent_keypair
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
        ws.send_text(
            _status_payload(
                command_id=command.id, status="failed", error_code="scan_failed"
            )
        )
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    assert command.status == "failed"
    assert command.error_code == "scan_failed"
    assert scan.status == "failed"


def test_unpublished_error_code_is_stored_verbatim_and_reads_unknown(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
    bearer_headers,
):
    private_key, _ = agent_keypair
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
        ws.send_text(
            _status_payload(
                command_id=command.id, status="failed", error_code="warp_core_breach"
            )
        )
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(command)
    assert command.status == "failed"
    assert command.error_code == "warp_core_breach"

    response = client.get(
        f"/api/v1/commands/{command.id}",
        headers=bearer_headers(seeded_org.id, "viewer"),
    )
    assert response.status_code == 200
    assert response.json()["error_code"] == "unknown"
