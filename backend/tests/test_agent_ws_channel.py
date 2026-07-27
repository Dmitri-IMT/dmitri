from __future__ import annotations

import json
from contextlib import ExitStack
from uuid import UUID

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.identity import Org
from api.services import agent_connections, device_sig
from conftest import ws_upgrade_headers
from sqlmodel import Session
from starlette.testclient import TestClient, WebSocketTestSession

COMMAND_ID = UUID("11111111-1111-4111-8111-111111111111")


def _ws_path(agent_id: UUID) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


def _hello_payload() -> str:
    return json.dumps(
        {
            "type": "hello",
            "agent_version": "0.2.0",
            "available_subnets": [{"interface": "eth0", "cidr": "10.0.0.0/24"}],
        }
    )


def _status_payload() -> str:
    return json.dumps(
        {
            "type": "status",
            "command_id": str(COMMAND_ID),
            "status": "running",
        }
    )


def _sync(ws: WebSocketTestSession) -> None:
    """Block until the server has drained every frame sent before this call.

    The handler processes frames sequentially in a single loop, so a reply to
    this sentinel proves the preceding frame was already handled. "not json"
    touches neither the registry nor the DB, so it is safe to use anywhere.
    """
    ws.send_text("not json")
    assert ws.receive_json()["type"] == "error"


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
    assert administrative_session.get(Agent, provisioned_agent.id).last_seen_at == (
        last_seen_after_hello.replace(tzinfo=None)
        if last_seen_after_hello is not None
        else None
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
        assert hello[1][0].interface == "eth0"
        assert hello[1][0].cidr == "10.0.0.0/24"

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


@pytest.mark.parametrize(
    "bad_frame",
    [
        "not json",
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
        ws_b.send_text(_status_payload())
        _sync(ws_b)
        assert agent_connections.last_seen_at(agent_b.id) is not None
