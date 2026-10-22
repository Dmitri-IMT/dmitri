from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from api.db.session import get_session
from api.main import app
from api.models.agent_update import AgentRelease, AgentUpdate, AgentUpdateEvent
from api.models.command import Agent, Command
from api.models.identity import Org
from api.models.persistence import ScanRecord
from api.services import agent_connections, agent_ws, device_sig
from api.services.agent_ws import handle_agent_frame
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


def _progress_payload(*, command_id: UUID, scan_id: UUID, sequence: int) -> str:
    return json.dumps(
        {
            "type": "progress",
            "command_id": str(command_id),
            "scan_id": str(scan_id),
            "sequence": sequence,
            "progress": {
                "stage": "discovery",
                "percent": 10,
                "machines": 2,
                "open_ports": None,
                "filtered_ports": None,
                "industrial_services": None,
                "vulnerabilities": None,
            },
        }
    )


def _sync(ws: WebSocketTestSession) -> None:
    """Block until the server has drained every frame sent before this call.

    The handler processes frames sequentially in a single loop, so a reply to
    this sentinel proves the preceding frame was already handled. "not json"
    touches neither the registry nor the DB, so it is safe to use anywhere.
    """
    ws.send_text("not json")
    assert ws.receive_json() == {"type": "error", "message": "invalid JSON"}


def _seed_scan(session: Session, org_id, *, agent_id=None) -> ScanRecord:
    scan = ScanRecord(
        scan_id=uuid4(),
        org_id=org_id,
        agent_id=agent_id,
        timestamp=T0,
        subnet="192.168.1.0/24",
        scan_mode="standard",
        status="pending",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def test_progress_frame_persists_snapshot_without_changing_command_status(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _ = agent_keypair
    scan = _seed_scan(
        administrative_session, seeded_org.id, agent_id=provisioned_agent.id
    )
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
            _progress_payload(command_id=command.id, scan_id=scan.scan_id, sequence=1)
        )
        _sync(ws)

    administrative_session.expire_all()
    administrative_session.refresh(scan)
    administrative_session.refresh(command)
    assert scan.progress_json is not None
    assert scan.progress_json["machines"] == 2
    assert scan.progress_seq == 1
    assert scan.progress_updated_at is not None
    assert command.status == "running"


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
        assert [(s.interface, s.cidr, s.is_default_route) for s in hello[1]] == [
            ("eth0", "10.0.0.0/24", False),
            ("wlan0", "192.168.1.0/24", True),
        ]

    administrative_session.refresh(provisioned_agent)
    assert provisioned_agent.last_seen_at is not None
    if initial_last_seen is not None:
        assert provisioned_agent.last_seen_at > initial_last_seen


def test_negotiated_hello_persists_observed_versions_and_returns_session(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    hello = json.loads(_hello_payload())
    hello.update(
        {
            "package_version": "1.0.7-1",
            "capabilities": ["scan_finalization_v1", "agent_update_v1"],
        }
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        session = ws.receive_json()
        connection = agent_connections.get_connection(provisioned_agent.id)
        assert connection is not None
        assert connection.capabilities == frozenset(
            {"scan_finalization_v1", "agent_update_v1"}
        )
        assert connection.protocol_version == 1

    assert session["type"] == "update_session"
    assert session["protocol_version"] == 1
    assert session["capabilities"] == [
        "scan_finalization_v1",
        "agent_update_v1",
    ]
    assert not agent_connections.is_online(provisioned_agent.id)
    assert agent_connections.get_hello(provisioned_agent.id) is None
    administrative_session.expire_all()
    persisted = administrative_session.get(Agent, provisioned_agent.id)
    assert persisted.observed_version == "0.2.0"
    assert persisted.observed_package_version == "1.0.7-1"
    assert persisted.version_observed_at is not None
    assert persisted.version_observed_session_id is not None


def test_agent_update_only_hello_negotiates_protocol_version(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _public_key = agent_keypair
    hello = json.loads(_hello_payload())
    hello.update(
        {
            "package_version": "1.0.7-1",
            "updater_version": "1",
            "os_suite": "trixie",
            "architecture": "arm64",
            "capabilities": ["agent_update_v1"],
        }
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        session = ws.receive_json()
        connection = agent_connections.get_connection(provisioned_agent.id)
        assert connection is not None
        assert connection.capabilities == frozenset({"agent_update_v1"})
        assert connection.protocol_version == session["protocol_version"] == 1

    assert session["capabilities"] == ["agent_update_v1"]


def test_matching_current_hello_confirms_durable_local_update_success(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _public_key = agent_keypair
    invocation_id = uuid4()
    update_id = uuid4()
    release = AgentRelease(
        source_commit="a" * 40,
        upstream_version="0.2.0",
        package_version="1.0.7-1",
        architecture="arm64",
        suite="trixie",
        sha256="b" * 64,
        size_bytes=123,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=T0,
    )
    operation = AgentUpdate(
        id=update_id,
        org_id=provisioned_agent.org_id,
        agent_id=provisioned_agent.id,
        actor_display_snapshot="admin@example.test",
        idempotency_key=str(uuid4()),
        request_digest="c" * 64,
        release_id=release.id,
        target_version="0.2.0",
        target_package_version="1.0.7-1",
        session_id=uuid4(),
        invocation_id=invocation_id,
        phase="awaiting_confirmation",
        local_outcome="succeeded",
        claimed_at=T0,
        local_completed_at=T0,
    )
    administrative_session.add_all(
        [
            release,
            operation,
            AgentUpdateEvent(
                update_id=update_id,
                sequence=1,
                body_digest="d" * 64,
                phase="awaiting_confirmation",
                local_outcome="succeeded",
                observed_version="0.2.0",
                observed_package_version="1.0.7-1",
                invocation_id=invocation_id,
                session_id=operation.session_id,
                occurred_at=T0,
                evidence_json={
                    "package_status": "configured",
                    "service_active": True,
                    "health_check": "passed",
                },
            ),
        ]
    )
    administrative_session.commit()
    hello = json.loads(_hello_payload())
    hello.update(
        {
            "agent_version": "0.2.0",
            "package_version": "1.0.7-1",
            "capabilities": ["scan_finalization_v1"],
            "update_context": {
                "update_id": str(update_id),
                "invocation_id": str(invocation_id),
            },
        }
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        session = ws.receive_json()
        assert session["type"] == "update_session"
        assert session["capabilities"] == ["scan_finalization_v1"]

    administrative_session.expire_all()
    confirmed = administrative_session.get(AgentUpdate, update_id)
    assert confirmed is not None
    assert confirmed.phase == "succeeded"
    assert confirmed.local_outcome == "succeeded"
    assert confirmed.confirmed_at is not None


def test_hello_with_mismatched_update_context_does_not_confirm(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
) -> None:
    private_key, _public_key = agent_keypair
    update_id = uuid4()
    invocation_id = uuid4()
    release = AgentRelease(
        source_commit="a" * 40,
        upstream_version="0.2.0",
        package_version="1.0.7-1",
        architecture="arm64",
        suite="trixie",
        sha256="b" * 64,
        size_bytes=123,
        required_protocol_version=1,
        required_updater_version=1,
        published_at=T0,
    )
    operation = AgentUpdate(
        id=update_id,
        org_id=provisioned_agent.org_id,
        agent_id=provisioned_agent.id,
        actor_display_snapshot="admin@example.test",
        idempotency_key=str(uuid4()),
        request_digest="c" * 64,
        release_id=release.id,
        target_version="0.2.0",
        target_package_version="1.0.7-1",
        session_id=uuid4(),
        invocation_id=invocation_id,
        phase="awaiting_confirmation",
        local_outcome="succeeded",
        claimed_at=T0,
        local_completed_at=T0,
    )
    administrative_session.add_all([release, operation])
    administrative_session.commit()
    hello = json.loads(_hello_payload())
    hello.update(
        {
            "agent_version": "0.2.0",
            "package_version": "1.0.7-1",
            "capabilities": ["agent_update_v1"],
            "update_context": {
                "update_id": str(update_id),
                "invocation_id": str(uuid4()),
            },
        }
    )

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        assert ws.receive_json()["type"] == "update_session"

    administrative_session.expire_all()
    unchanged = administrative_session.get(AgentUpdate, update_id)
    assert unchanged is not None
    assert unchanged.phase == "awaiting_confirmation"
    assert unchanged.confirmed_at is None


def test_legacy_hello_keeps_last_observed_package_version(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    provisioned_agent.observed_package_version = "1.0.7-1"
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_text(_hello_payload())
        _sync(ws)

    administrative_session.expire_all()
    persisted = administrative_session.get(Agent, provisioned_agent.id)
    assert persisted.observed_version == "0.2.0"
    assert persisted.observed_package_version == "1.0.7-1"


def test_terminal_status_ack_follows_persisted_terminal_state(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    scan = _seed_scan(
        administrative_session, seeded_org.id, agent_id=provisioned_agent.id
    )
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="running",
        scan_id=scan.scan_id,
    )
    hello = json.loads(_hello_payload())
    hello["capabilities"] = ["scan_finalization_v1"]

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        session = ws.receive_json()
        ws.send_text(_status_payload(command_id=command.id, status="failed"))
        acknowledgement = ws.receive_json()

    administrative_session.expire_all()
    persisted = administrative_session.get(Command, command.id)
    assert persisted.status == "failed"
    assert acknowledgement == {
        "type": "scan_status_ack",
        "session_id": session["session_id"],
        "command_id": str(command.id),
        "status": "failed",
        "has_results": False,
    }


def test_duplicate_terminal_status_gets_ack_of_effective_status(
    client: TestClient,
    administrative_session: Session,
    provisioned_agent: Agent,
    seeded_org: Org,
    agent_keypair,
):
    private_key, _public_key = agent_keypair
    scan = _seed_scan(
        administrative_session, seeded_org.id, agent_id=provisioned_agent.id
    )
    scan.status = "completed"
    administrative_session.add(scan)
    command = _seed_command(
        administrative_session,
        org_id=seeded_org.id,
        agent_id=provisioned_agent.id,
        status="done",
        scan_id=scan.scan_id,
    )
    hello = json.loads(_hello_payload())
    hello["capabilities"] = ["scan_finalization_v1"]

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        ws.send_json(hello)
        session = ws.receive_json()
        ws.send_text(_status_payload(command_id=command.id, status="done"))
        acknowledgement = ws.receive_json()

    assert acknowledgement["type"] == "scan_status_ack"
    assert acknowledgement["session_id"] == session["session_id"]
    assert acknowledgement["status"] == "done"
    assert acknowledgement["has_results"] is True


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


def test_replaced_socket_status_is_ignored_before_database_work():
    stale_socket = AsyncMock()
    current_socket = AsyncMock()
    session_factory = AsyncMock(side_effect=AssertionError("stale socket touched DB"))

    async def run():
        await agent_connections.register(provisioned_agent_id, stale_socket, now=T0)
        await agent_connections.register(provisioned_agent_id, current_socket, now=T0)
        await handle_agent_frame(
            session_factory,
            stale_socket,
            agent_id=provisioned_agent_id,
            raw_text=_status_payload(status="done"),
            now=T0,
        )

    provisioned_agent_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    asyncio.run(run())

    session_factory.assert_not_called()
    stale_socket.send_text.assert_not_awaited()


def test_terminal_status_processing_failure_sends_no_ack(monkeypatch):
    websocket = AsyncMock()
    agent_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    async def failed_commit(*args, **kwargs):
        raise RuntimeError("database commit failed")

    monkeypatch.setattr(agent_ws, "_apply_status_frame", failed_commit)

    async def run():
        await agent_connections.register(agent_id, websocket, now=T0)
        await agent_connections.set_hello(
            agent_id,
            websocket,
            agent_version="1.0.0",
            available_subnets=[],
            capabilities=frozenset({"scan_finalization_v1"}),
            now=T0,
        )
        await handle_agent_frame(
            AsyncMock(),
            websocket,
            agent_id=agent_id,
            raw_text=_status_payload(status="done"),
            now=T0,
        )

    with pytest.raises(RuntimeError, match="database commit failed"):
        asyncio.run(run())

    websocket.send_text.assert_not_awaited()


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


def test_revoked_agent_status_frame_closes_socket_and_applies_nothing(
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

    with client.websocket_connect(
        _ws_path(provisioned_agent.id),
        headers=ws_upgrade_headers(private_key, provisioned_agent.id),
    ) as ws:
        _sync(ws)
        provisioned_agent.revoked_at = T0
        administrative_session.add(provisioned_agent)
        administrative_session.commit()

        ws.send_text(_status_payload(command_id=command.id, status="running"))
        assert ws.receive() == {
            "type": "websocket.close",
            "code": 4001,
            "reason": "revoked",
        }

    assert not agent_connections.is_online(provisioned_agent.id)
    administrative_session.expire_all()
    administrative_session.refresh(command)
    administrative_session.refresh(scan)
    administrative_session.refresh(provisioned_agent)
    assert command.status == "queued"
    assert command.delivered_at is None
    assert command.started_at is None
    assert scan.status == "pending"
    assert provisioned_agent.connected_at is None
