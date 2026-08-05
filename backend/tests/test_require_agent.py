from __future__ import annotations

import asyncio
import hmac
import typing
from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from api.db.session import get_session
from api.dependencies import agent_auth
from api.dependencies.agent_auth import (
    AgentIdentity,
    AgentRevoked,
    AgentUnauthenticated,
    authenticate_agent,
    require_agent,
)
from api.main import app as main_app
from api.models.command import Agent
from api.models.persistence import utc_now
from api.services import device_sig
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.testclient import TestClient
from sqlmodel import Session

app = FastAPI()


@app.post("/agent-echo")
async def agent_echo(
    identity: AgentIdentity = Depends(require_agent),
) -> AgentIdentity:
    return identity


def _headers(
    *,
    private_key: bytes,
    device_id,
    method: str = "POST",
    path: str = "/agent-echo",
    body: bytes = b"",
    timestamp=None,
    nonce: str | None = None,
) -> dict[str, str]:
    timestamp_str = (timestamp or utc_now()).isoformat()
    nonce_value = nonce or uuid4().hex
    body_hash = device_sig.body_sha256(body)
    canonical = device_sig.canonical_string(
        method, path, str(device_id), timestamp_str, nonce_value, body_hash
    )
    signature = device_sig.sign(private_key, canonical)
    return {
        "X-Device-Id": str(device_id),
        "X-Timestamp": timestamp_str,
        "X-Nonce": nonce_value,
        "X-Body-SHA256": body_hash,
        "X-Signature": signature,
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


def test_valid_signature_passes(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(private_key=private_key, device_id=provisioned_agent.id)

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == str(provisioned_agent.id)
    assert body["org_id"] == str(provisioned_agent.org_id)


def test_bad_signature_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    other_private_key, _ = device_sig.generate_keypair()
    headers = _headers(private_key=other_private_key, device_id=provisioned_agent.id)

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_tampered_body_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=b"original"
    )

    response = client.post(
        "/agent-echo", headers=headers, content=b"tampered-body-content"
    )

    assert response.status_code == 401


def test_unknown_device_refused(client: TestClient, agent_keypair):
    private_key, _public_key = agent_keypair
    headers = _headers(private_key=private_key, device_id=uuid4())

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "missing_header",
    ["X-Device-Id", "X-Timestamp", "X-Nonce", "X-Body-SHA256", "X-Signature"],
)
def test_missing_header_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair, missing_header
):
    private_key, _public_key = agent_keypair
    headers = _headers(private_key=private_key, device_id=provisioned_agent.id)
    del headers[missing_header]

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_stale_timestamp_plus_six_minutes_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        timestamp=utc_now() + timedelta(minutes=6),
    )

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_stale_timestamp_minus_six_minutes_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        timestamp=utc_now() - timedelta(minutes=6),
    )

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_timestamp_minus_four_minutes_passes(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        timestamp=utc_now() - timedelta(minutes=4),
    )

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 200


def test_replay_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(private_key=private_key, device_id=provisioned_agent.id)

    first = client.post("/agent-echo", headers=headers)
    second = client.post("/agent-echo", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 401


def test_revoked_device_refused_with_403_not_401(
    client: TestClient,
    provisioned_agent: Agent,
    agent_keypair,
    administrative_session: Session,
):
    private_key, _public_key = agent_keypair
    provisioned_agent.revoked_at = utc_now()
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    headers = _headers(private_key=private_key, device_id=provisioned_agent.id)
    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 403
    assert response.status_code != 401


def test_device_cannot_claim_org(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    body = f'{{"org_id": "{uuid4()}"}}'.encode()
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=body
    )

    response = client.post("/agent-echo", headers=headers, content=body)

    assert response.status_code == 200
    assert response.json()["org_id"] == str(provisioned_agent.org_id)


def test_core_valid_request_with_empty_body_resolves_identity(
    administrative_session: Session, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=b""
    )

    identity = authenticate_agent(
        administrative_session,
        method="POST",
        path="/agent-echo",
        headers=headers,
        body=b"",
        now=utc_now(),
    )

    assert identity.agent_id == provisioned_agent.id
    assert identity.org_id == provisioned_agent.org_id


def test_core_expected_agent_id_mismatch_raises_unauthenticated(
    administrative_session: Session, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=b""
    )

    identity = authenticate_agent(
        administrative_session,
        method="POST",
        path="/agent-echo",
        headers=headers,
        body=b"",
        now=utc_now(),
        expected_agent_id=provisioned_agent.id,
    )
    assert identity.agent_id == provisioned_agent.id

    with pytest.raises(AgentUnauthenticated):
        authenticate_agent(
            administrative_session,
            method="POST",
            path="/agent-echo",
            headers=_headers(
                private_key=private_key,
                device_id=provisioned_agent.id,
                body=b"",
            ),
            body=b"",
            now=utc_now(),
            expected_agent_id=uuid4(),
        )


def test_bad_signature_does_not_burn_nonce_for_later_valid_replay(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    other_private_key, _ = device_sig.generate_keypair()
    timestamp = utc_now()
    nonce = uuid4().hex

    bad_headers = _headers(
        private_key=other_private_key,
        device_id=provisioned_agent.id,
        timestamp=timestamp,
        nonce=nonce,
    )
    failed = client.post("/agent-echo", headers=bad_headers)
    assert failed.status_code == 401

    good_headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        timestamp=timestamp,
        nonce=nonce,
    )
    retried = client.post("/agent-echo", headers=good_headers)
    assert retried.status_code == 200


def test_malformed_device_id_refused(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    headers = _headers(private_key=private_key, device_id=provisioned_agent.id)
    headers["X-Device-Id"] = "not-a-uuid"

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_naive_timestamp_refused_with_401_not_500(
    client: TestClient, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    naive_timestamp = utc_now().replace(tzinfo=None)
    headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        timestamp=naive_timestamp,
    )

    response = client.post("/agent-echo", headers=headers)

    assert response.status_code == 401


def test_core_naive_timestamp_raises_agent_unauthenticated(
    administrative_session: Session, provisioned_agent: Agent, agent_keypair
):
    private_key, _public_key = agent_keypair
    naive_timestamp = utc_now().replace(tzinfo=None)
    headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        body=b"",
        timestamp=naive_timestamp,
    )

    with pytest.raises(AgentUnauthenticated):
        authenticate_agent(
            administrative_session,
            method="POST",
            path="/agent-echo",
            headers=headers,
            body=b"",
            now=utc_now(),
        )


def test_skew_window_read_from_settings_not_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
):
    private_key, _public_key = agent_keypair

    class _NarrowSkewSettings:
        device_sig_max_skew_seconds = 30

    monkeypatch.setattr(agent_auth, "get_settings", lambda: _NarrowSkewSettings())

    inside_headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        body=b"",
        timestamp=utc_now() - timedelta(seconds=20),
    )
    identity = authenticate_agent(
        administrative_session,
        method="POST",
        path="/agent-echo",
        headers=inside_headers,
        body=b"",
        now=utc_now(),
    )
    assert identity.agent_id == provisioned_agent.id

    outside_headers = _headers(
        private_key=private_key,
        device_id=provisioned_agent.id,
        body=b"",
        timestamp=utc_now() - timedelta(seconds=40),
    )
    with pytest.raises(AgentUnauthenticated):
        authenticate_agent(
            administrative_session,
            method="POST",
            path="/agent-echo",
            headers=outside_headers,
            body=b"",
            now=utc_now(),
        )


def test_body_hash_and_signature_verified_via_constant_time_helpers(
    administrative_session: Session,
    provisioned_agent: Agent,
    agent_keypair,
    monkeypatch: pytest.MonkeyPatch,
):
    """authenticate_agent must compare the body hash with hmac.compare_digest
    and verify the signature via device_sig.verify -- not a naive `==` -- so
    neither comparison leaks timing information. Spying on the real
    implementations (instead of grepping source for the call text) proves
    they are actually invoked on a valid request, and survives any harmless
    rename, comment, or reformat."""
    private_key, _public_key = agent_keypair
    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=b""
    )

    compare_digest = Mock(wraps=hmac.compare_digest)
    monkeypatch.setattr(hmac, "compare_digest", compare_digest)

    verify = Mock(wraps=device_sig.verify)
    monkeypatch.setattr(device_sig, "verify", verify)

    identity = authenticate_agent(
        administrative_session,
        method="POST",
        path="/agent-echo",
        headers=headers,
        body=b"",
        now=utc_now(),
    )

    assert identity.agent_id == provisioned_agent.id
    compare_digest.assert_called_once()
    verify.assert_called_once()


def test_core_signature_has_no_fastapi_types():
    """authenticate_agent is the framework-independent core: none of its
    parameter or return annotations may reference a fastapi type. Checking
    the resolved type hints (rather than grepping source text) survives a
    docstring that happens to mention "request" or "fastapi"."""
    hints = typing.get_type_hints(authenticate_agent)
    assert hints, "expected authenticate_agent to carry type annotations"
    for name, hint in hints.items():
        module = getattr(hint, "__module__", "") or ""
        assert not module.startswith("fastapi"), (
            f"{name!r} is annotated with a fastapi type: {hint!r}"
        )


def test_core_revoked_device_raises_agent_revoked_not_http_exception(
    administrative_session: Session, provisioned_agent: Agent, agent_keypair
):
    """The core raises the plain domain exception AgentRevoked for a revoked
    device; only the require_agent adapter maps it onto an HTTPException.
    Calling authenticate_agent directly and asserting on the raised exception
    type is a genuine proof that no HTTP/fastapi coupling leaked into the
    core, unlike trusting that its source text never mentions HTTPException."""
    private_key, _public_key = agent_keypair
    provisioned_agent.revoked_at = utc_now()
    administrative_session.add(provisioned_agent)
    administrative_session.commit()

    headers = _headers(
        private_key=private_key, device_id=provisioned_agent.id, body=b""
    )

    with pytest.raises(AgentRevoked):
        authenticate_agent(
            administrative_session,
            method="POST",
            path="/agent-echo",
            headers=headers,
            body=b"",
            now=utc_now(),
        )


def test_require_agent_delegates_fully_to_authenticate_agent(
    client: TestClient, provisioned_agent: Agent, monkeypatch: pytest.MonkeyPatch
):
    """require_agent must hold no skew/signature/nonce logic of its own -- it
    only unpacks the Request and maps AgentRevoked/AgentUnauthenticated onto
    HTTPException. Stubbing out authenticate_agent and sending headers that
    would fail every real check proves the adapter never second-guesses the
    core: the stub's return value/exception alone decides the response."""
    garbage_headers = {
        "X-Device-Id": "not-a-uuid",
        "X-Timestamp": "not-a-timestamp",
        "X-Nonce": "",
        "X-Body-SHA256": "not-a-hash",
        "X-Signature": "not-a-signature",
    }

    def _stub_success(session, **kwargs):
        return AgentIdentity(
            agent_id=provisioned_agent.id, org_id=provisioned_agent.org_id
        )

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_success)
    ok_response = client.post("/agent-echo", headers=garbage_headers)
    assert ok_response.status_code == 200
    assert ok_response.json()["agent_id"] == str(provisioned_agent.id)

    def _stub_revoked(session, **kwargs):
        raise AgentRevoked("device is revoked")

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_revoked)
    revoked_response = client.post("/agent-echo", headers=garbage_headers)
    assert revoked_response.status_code == 403

    def _stub_unauthenticated(session, **kwargs):
        raise AgentUnauthenticated("nope")

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_unauthenticated)
    unauth_response = client.post("/agent-echo", headers=garbage_headers)
    assert unauth_response.status_code == 401


def test_require_agent_ws_delegates_fully_to_authenticate_agent(
    monkeypatch: pytest.MonkeyPatch,
):
    agent_id = uuid4()
    org_id = uuid4()
    expected_path = f"/api/v1/agents/{agent_id}/commands"
    session = Mock()
    websocket = Mock(spec=WebSocket)
    websocket.url = Mock()
    websocket.url.path = expected_path
    websocket.headers = {}
    websocket.accept = Mock()
    captured: dict = {}

    def _stub_success(session_arg, **kwargs):
        captured["session"] = session_arg
        captured.update(kwargs)
        return AgentIdentity(agent_id=agent_id, org_id=org_id)

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_success)
    identity = asyncio.run(
        agent_auth.require_agent_ws(websocket, agent_id, session=session)
    )
    assert identity.agent_id == agent_id
    assert captured["session"] is session
    assert captured["method"] == "GET"
    assert captured["path"] == expected_path
    assert captured["headers"] is websocket.headers
    assert captured["body"] == b""
    assert captured["expected_agent_id"] == agent_id
    websocket.accept.assert_not_called()

    def _stub_revoked(session_arg, **kwargs):
        raise AgentRevoked("device is revoked")

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_revoked)
    with pytest.raises(HTTPException) as revoked_exc:
        asyncio.run(agent_auth.require_agent_ws(websocket, agent_id, session=session))
    assert revoked_exc.value.status_code == 403

    def _stub_unauthenticated(session_arg, **kwargs):
        raise AgentUnauthenticated("nope")

    monkeypatch.setattr(agent_auth, "authenticate_agent", _stub_unauthenticated)
    with pytest.raises(HTTPException) as unauth_exc:
        asyncio.run(agent_auth.require_agent_ws(websocket, agent_id, session=session))
    assert unauth_exc.value.status_code == 401


def test_ingest_scan_route_mounts_require_agent():
    seen: set = set()
    stack = list(main_app.routes)
    while stack:
        route = stack.pop()
        included_router = getattr(route, "original_router", None)
        if included_router is not None:
            stack.extend(included_router.routes)
            continue
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        pending = [dependant]
        while pending:
            current = pending.pop()
            if current.call is not None:
                seen.add(current.call)
            pending.extend(current.dependencies)

    assert require_agent in seen
