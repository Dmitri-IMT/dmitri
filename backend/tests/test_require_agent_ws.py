from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.command import Agent
from api.models.persistence import utc_now
from api.services import agent_connections, device_sig
from conftest import ws_upgrade_headers
from sqlmodel import Session
from starlette.testclient import TestClient, WebSocketDenialResponse


def _ws_path(agent_id: UUID) -> str:
    return f"/api/v1/agents/{agent_id}/commands"


def _assert_ws_denial_envelope(
    denial: WebSocketDenialResponse, status_code: int, code: str
) -> None:
    assert denial.status_code == status_code
    body = denial.json()
    assert "detail" not in body
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["details"] == {}


@pytest.fixture
def client(administrative_session: Session) -> TestClient:
    def _override_get_session():
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_valid_upgrade_marks_agent_online(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)

    with client.websocket_connect(
        _ws_path(provisioned_agent.id), headers=headers
    ):
        assert agent_connections.is_online(provisioned_agent.id)
        assert agent_connections.last_seen_at(provisioned_agent.id) is not None


def test_bad_signature_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    other_private_key, _ = device_sig.generate_keypair()
    headers = ws_upgrade_headers(other_private_key, provisioned_agent.id)

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(provisioned_agent.id), headers=headers
        ):
            pass

    _assert_ws_denial_envelope(exc_info.value, 401, "unauthorized")
    assert not agent_connections.is_online(provisioned_agent.id)


def test_stale_timestamp_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    stale = utc_now() - timedelta(minutes=6)
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    headers["X-Timestamp"] = stale.isoformat()
    canonical = device_sig.canonical_string(
        "GET",
        _ws_path(provisioned_agent.id),
        str(provisioned_agent.id),
        headers["X-Timestamp"],
        headers["X-Nonce"],
        headers["X-Body-SHA256"],
    )
    headers["X-Signature"] = device_sig.sign(private_key, canonical)

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(provisioned_agent.id), headers=headers
        ):
            pass

    assert exc_info.value.status_code == 401
    assert not agent_connections.is_online(provisioned_agent.id)


def test_replay_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)

    with client.websocket_connect(
        _ws_path(provisioned_agent.id), headers=headers
    ):
        pass

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(provisioned_agent.id), headers=headers
        ):
            pass

    assert exc_info.value.status_code == 401
    assert not agent_connections.is_online(provisioned_agent.id)


@pytest.mark.parametrize(
    "missing_header",
    ["X-Device-Id", "X-Timestamp", "X-Nonce", "X-Body-SHA256", "X-Signature"],
)
def test_missing_header_refused(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
    missing_header: str,
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    del headers[missing_header]

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(provisioned_agent.id), headers=headers
        ):
            pass

    assert exc_info.value.status_code == 401
    assert not agent_connections.is_online(provisioned_agent.id)


def test_revoked_device_refused_with_403(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
    administrative_session: Session,
):
    private_key, _public_key = agent_keypair
    provisioned_agent.revoked_at = utc_now()
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    headers = ws_upgrade_headers(private_key, provisioned_agent.id)

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(provisioned_agent.id), headers=headers
        ):
            pass

    _assert_ws_denial_envelope(exc_info.value, 403, "forbidden")
    assert not agent_connections.is_online(provisioned_agent.id)


def test_path_header_mismatch_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    other_agent_id = uuid4()
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(
            _ws_path(other_agent_id), headers=headers
        ):
            pass

    assert exc_info.value.status_code == 401
    assert not agent_connections.is_online(provisioned_agent.id)
    assert not agent_connections.is_online(other_agent_id)


def test_malformed_agent_id_path_refused_without_burning_nonce(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = ws_upgrade_headers(private_key, provisioned_agent.id)
    malformed_path = "/api/v1/agents/not-a-uuid/commands"

    with pytest.raises(WebSocketDenialResponse) as exc_info:
        with client.websocket_connect(malformed_path, headers=headers):
            pass

    _assert_ws_denial_envelope(exc_info.value, 403, "forbidden")
    assert not agent_connections.is_online(provisioned_agent.id)

    with client.websocket_connect(
        _ws_path(provisioned_agent.id), headers=headers
    ):
        assert agent_connections.is_online(provisioned_agent.id)
