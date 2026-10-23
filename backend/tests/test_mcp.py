from __future__ import annotations

import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from api.core.config import Settings, get_settings
from api.mcp_server import create_mcp_server
from api.models.identity import Org, User
from api.models.mcp import (
    McpAuthorization,
    McpClient,
    McpConnection,
    McpCredential,
)
from api.models.persistence import HostRecord, ScanHostRecord, ScanRecord, utc_now
from api.routers import mcp as mcp_routes
from api.services import mcp_auth, mcp_reads
from api.services.tokens import create_access_token, hash_token
from fastapi import FastAPI
from pydantic import ValidationError
from read_factories import make_finding, make_host, make_scan, make_scan_host
from sqlalchemy import text
from sqlmodel import select
from starlette.testclient import TestClient
from test_industrial_persistence import SAMPLE_DIGEST, _host, _persist, _scan

RESOURCE = "http://127.0.0.1:8000/mcp"
CALLBACK = "http://127.0.0.1:8917/callback"
VERIFIER = "a" * 64
CHALLENGE = base64.urlsafe_b64encode(
    hashlib.sha256(VERIFIER.encode()).digest()
).decode().rstrip("=")


@pytest.fixture
def mcp_client(monkeypatch, migrated_database):
    settings = get_settings().model_copy(update={
        "mcp_public_url": RESOURCE, "app_base_url": "http://localhost:5173",
    })
    monkeypatch.setattr(mcp_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(mcp_reads, "get_settings", lambda: settings)
    monkeypatch.setattr(mcp_routes, "get_settings", lambda: settings)
    server, application = create_mcp_server()

    @asynccontextmanager
    async def lifespan(app):
        async with server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(mcp_routes.router)
    app.mount("/", application)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


@pytest.fixture
def member(administrative_session, seeded_org):
    user = User(
        org_id=seeded_org.id, email="mcp@example.test", role="admin",
        password_hash="x",  # unused: these tests never authenticate
    )
    administrative_session.add(user)
    administrative_session.commit()
    administrative_session.refresh(user)
    return user


def web_headers(user):
    token = create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


def start_authorization(client, *, redirect_uri=CALLBACK):
    registered = client.post("/register", json={
        "client_name": "Local Codex", "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "scope": "dmitri:read",
    })
    assert registered.status_code == 201, registered.text
    client_id = registered.json()["client_id"]
    response = client.get("/authorize", params={
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "code_challenge": CHALLENGE,
        "code_challenge_method": "S256", "resource": RESOURCE,
        "scope": "dmitri:read", "state": "test-state",
    }, follow_redirects=False)
    assert response.status_code == 302, response.text
    pending = parse_qs(urlsplit(response.headers["location"]).query)["request"][0]
    return client_id, pending


def connect(client, user):
    client_id, pending = start_authorization(client)
    headers = web_headers(user)
    info = client.get("/api/v1/mcp/authorization", params={
        "request_token": pending,
    }, headers=headers)
    assert info.status_code == 200, info.text
    assert info.json()["email"] == user.email
    response = client.post("/api/v1/mcp/authorization", headers=headers, json={
        "request_token": pending, "approve": True,
    })
    assert response.status_code == 200, response.text
    query = parse_qs(urlsplit(response.json()["redirect_url"]).query)
    assert query["state"] == ["test-state"]
    assert query["iss"] == ["http://127.0.0.1:8000/"]
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert query["iss"] == [metadata["issuer"]]
    assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
    data = {
        "grant_type": "authorization_code", "client_id": client_id,
        "code": query["code"][0], "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER, "resource": RESOURCE,
    }
    response = client.post("/token", data=data)
    assert response.status_code == 200, response.text
    return client_id, response.json(), data


def rpc(client, token, method, params=None):
    return client.post("/mcp", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
    }, json={
        "jsonrpc": "2.0", "id": 1, "method": method,
        **({"params": params} if params is not None else {}),
    })


def read_tool(client, token, name, arguments=None):
    response = rpc(client, token, "tools/call", {
        "name": name, "arguments": arguments or {},
    })
    assert response.status_code == 200, response.text
    return response.json()["result"]


@pytest.mark.parametrize("role", ["admin", "viewer"])
def test_discovery_authentication_and_read_only_tools(
    mcp_client, member, administrative_session, role,
):
    member.role = role
    administrative_session.add(member)
    administrative_session.commit()
    metadata = mcp_client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == RESOURCE
    unauthorized = mcp_client.post("/mcp", json={})
    assert unauthorized.status_code == 401
    assert "resource_metadata=" in unauthorized.headers["www-authenticate"]
    _, tokens, _ = connect(mcp_client, member)
    token = tokens["access_token"]
    initialized = rpc(mcp_client, token, "initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    })
    assert initialized.status_code == 200, initialized.text
    assert initialized.json()["result"]["serverInfo"]["name"] == "Dmitri"
    response = rpc(mcp_client, token, "tools/list")
    tools = response.json()["result"]["tools"]
    assert len(tools) == 9
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    assert all(not tool["annotations"]["destructiveHint"] for tool in tools)
    context = read_tool(mcp_client, token, "get_account_context")
    assert "structuredContent" in context, context
    assert context["structuredContent"]["data"]["email"] == member.email
    assert context["structuredContent"]["data"]["scope"] == "dmitri:read"


def test_pkce_resource_and_single_use_code(mcp_client, member):
    _, tokens, exchange = connect(mcp_client, member)
    invalid_resource = mcp_client.post("/token", data={
        **exchange, "resource": "https://other.example/mcp",
    })
    assert invalid_resource.status_code == 400
    bad_pkce = mcp_client.post("/token", data={
        **exchange, "code_verifier": "b" * 64,
    })
    assert bad_pkce.status_code == 400
    assert mcp_auth.load_access_token(tokens["access_token"]) is not None
    replay = mcp_client.post("/token", data=exchange)
    assert replay.status_code == 400
    assert mcp_auth.load_access_token(tokens["access_token"]) is None


def test_refresh_rotation_and_reuse_revoke_connection(mcp_client, member):
    client_id, tokens, _ = connect(mcp_client, member)
    payload = {
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
    }
    response = mcp_client.post("/token", data=payload)
    assert response.status_code == 200, response.text
    rotated = response.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert mcp_auth.load_access_token(rotated["access_token"]) is not None
    assert mcp_client.post("/token", data=payload).status_code == 400
    assert mcp_auth.load_access_token(rotated["access_token"]) is None


def test_deny_consent_and_reject_unsafe_callbacks(
    mcp_client, member, administrative_session,
):
    for callback in (
        "https://evil.example/callback",
        "http://127.0.0.1.evil.example/callback",
        "http://127.0.0.1/callback#fragment",
    ):
        response = mcp_client.post("/register", json={
            "redirect_uris": [callback], "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
        })
        assert response.status_code == 400
    _, pending = start_authorization(mcp_client)
    response = mcp_client.post(
        "/api/v1/mcp/authorization", headers=web_headers(member), json={
        "request_token": pending, "approve": False,
        },
    )
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["redirect_url"]).query)
    assert query["error"] == ["access_denied"]
    assert administrative_session.exec(select(McpConnection)).all() == []
    repeated = mcp_client.post(
        "/api/v1/mcp/authorization", headers=web_headers(member), json={
        "request_token": pending, "approve": True,
        },
    )
    assert repeated.status_code == 409


def test_disconnect_and_membership_change(mcp_client, member, administrative_session):
    _, tokens, _ = connect(mcp_client, member)
    headers = web_headers(member)
    response = mcp_client.get("/api/v1/mcp/connections", headers=headers)
    connection_id = response.json()["data"][0]["id"]
    unknown = mcp_client.delete(
        f"/api/v1/mcp/connections/{uuid4()}", headers=headers
    )
    assert unknown.status_code == 404
    disconnected = mcp_client.delete(
        f"/api/v1/mcp/connections/{connection_id}", headers=headers
    )
    assert disconnected.status_code == 204
    assert rpc(mcp_client, tokens["access_token"], "tools/list").status_code == 401
    _, tokens, _ = connect(mcp_client, member)
    other = Org(name="Other")
    administrative_session.add(other)
    administrative_session.commit()
    member.org_id = other.id
    administrative_session.add(member)
    administrative_session.commit()
    assert rpc(mcp_client, tokens["access_token"], "tools/list").status_code == 401


def test_mcp_credentials_cannot_authorize_web_writes(mcp_client, member, client):
    _, tokens, _ = connect(mcp_client, member)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    for path in ("/api/v1/scans", "/api/v1/hosts", "/api/v1/users/me"):
        assert client.delete(path, headers=headers).status_code == 401
    assert client.get("/api/v1/scans", headers=headers).status_code == 401
    web_token = web_headers(member)["Authorization"][7:]
    assert rpc(mcp_client, web_token, "tools/list").status_code == 401


def test_scan_reads_are_organization_scoped_and_historical(
    mcp_client, member, administrative_session,
):
    other = Org(name="Foreign")
    administrative_session.add(other)
    administrative_session.commit()
    scans = [ScanRecord(
        scan_id=uuid4(), org_id=org_id, timestamp=utc_now(),
        subnet="192.168.1.0/24", scan_mode="nspi",
    ) for org_id in (member.org_id, other.id)]
    administrative_session.add_all(scans)
    administrative_session.commit()
    host = HostRecord(
        org_id=member.org_id, identity_key="ip:192.168.1.10",
        ip="192.168.1.20", hostname="current-name", mac=None,
        vendor="Current", first_seen_at=utc_now(), last_seen_at=utc_now(),
        open_ports_count=0,
    )
    administrative_session.add(host)
    administrative_session.commit()
    historical = ScanHostRecord(
        scan_id=scans[0].scan_id, host_id=host.id, ip="192.168.1.10",
        hostname="historical-name", vendor="Historical",
    )
    administrative_session.add(historical)
    administrative_session.commit()
    _, tokens, _ = connect(mcp_client, member)
    token = tokens["access_token"]
    listed = read_tool(mcp_client, token, "list_scans", {
        "scan_mode": "nspi", "per_page": 1,
    })
    data = listed["structuredContent"]["data"]
    assert data["total"] == 1
    assert data["items"][0]["scan_id"] == str(scans[0].scan_id)
    for scan_id in (scans[1].scan_id, uuid4()):
        response = read_tool(mcp_client, token, "get_scan", {"scan_id": str(scan_id)})
        assert response["isError"] is True
        assert response["content"][0]["text"].endswith("Scan not found.")
    response = read_tool(mcp_client, token, "get_scan_machine", {
        "scan_id": str(scans[0].scan_id), "machine_id": str(host.id),
    })
    assert response["structuredContent"]["data"]["hostname"] == "historical-name"
    response = read_tool(mcp_client, token, "get_machine", {
        "machine_id": str(host.id),
    })
    assert response["structuredContent"]["data"]["hostname"] == "current-name"
    invalid_page = read_tool(mcp_client, token, "list_scans", {"per_page": 26})
    assert invalid_page["isError"] is True


def test_tokens_are_hashed_and_expire(mcp_client, member, administrative_session):
    _, tokens, _ = connect(mcp_client, member)
    credential = administrative_session.get(
        McpCredential, hash_token(tokens["access_token"])
    )
    assert credential is not None
    assert credential.token_hash != tokens["access_token"]
    credential.expires_at = utc_now() - timedelta(seconds=1)
    administrative_session.add(credential)
    administrative_session.commit()
    assert rpc(mcp_client, tokens["access_token"], "tools/list").status_code == 401
    pending = administrative_session.exec(select(McpAuthorization)).one()
    assert pending.exchanged_at is not None


def test_bounded_results_flag_truncation():
    result = mcp_reads.bounded_result({
        "evidence": "x" * 200000, "units": list(range(1000)),
    })
    assert result["truncated"] is True
    assert "data.evidence" in result["truncated_fields"]
    assert "data.units" in result["truncated_fields"]
    assert len(result["data"]["units"]) == 100


def test_reads_uploaded_modbus_observations(
    mcp_client, member, administrative_session, seeded_org, provisioned_agent,
):
    scan = _scan([_host()])
    _persist(administrative_session, scan, seeded_org, provisioned_agent)
    host = administrative_session.exec(select(HostRecord)).one()
    _, tokens, _ = connect(mcp_client, member)
    response = read_tool(mcp_client, tokens["access_token"], "get_scan_machine", {
        "scan_id": str(scan.scan_id), "machine_id": str(host.id),
        "section": "industrial_services", "port": 502, "unit_id": 1,
    })
    data = response["structuredContent"]["data"]
    unit = data["items"][0]["units"][0]
    assert unit["identification"]["product_name"] == "Modicon M580"
    assert unit["address_ranges"][0]["value_digest"] == SAMPLE_DIGEST
    assert data["scan_id"] == str(scan.scan_id)
    assert data["source_url"].endswith(f"/scans/{scan.scan_id}")
    assert response["structuredContent"]["truncated"] is False


def test_finding_evidence_pages_and_foreign_records(
    mcp_client, member, administrative_session,
):
    scan = make_scan(administrative_session, member.org_id, scan_mode="nspi")
    machine = make_host(administrative_session, member.org_id, "192.168.1.10")
    observed = make_scan_host(
        administrative_session, scan.scan_id, machine.id, "192.168.1.10"
    )
    finding = make_finding(
        administrative_session, scan.scan_id, observed.id, "mcp-evidence"
    )
    evidence = "evidence_" * 700
    finding.evidence = evidence
    administrative_session.add(finding)
    foreign = Org(name="Foreign findings")
    administrative_session.add(foreign)
    administrative_session.commit()
    foreign_scan = make_scan(administrative_session, foreign.id)
    foreign_machine = make_host(
        administrative_session, foreign.id, "192.168.2.10"
    )
    foreign_observed = make_scan_host(
        administrative_session, foreign_scan.scan_id,
        foreign_machine.id, "192.168.2.10",
    )
    foreign_finding = make_finding(
        administrative_session, foreign_scan.scan_id,
        foreign_observed.id, "foreign-mcp-evidence",
    )
    _, tokens, _ = connect(mcp_client, member)
    token = tokens["access_token"]
    listed = read_tool(mcp_client, token, "list_findings")
    assert listed["structuredContent"]["data"]["total"] == 1
    first = read_tool(mcp_client, token, "get_finding", {
        "finding_id": str(finding.finding_id),
    })["structuredContent"]["data"]
    assert first["confidence"] == "tentative"
    assert first["evidence_status"] == "unknown"
    assert first["next_evidence_offset"] == 4000
    second = read_tool(mcp_client, token, "get_finding", {
        "finding_id": str(finding.finding_id), "evidence_offset": 4000,
    })["structuredContent"]["data"]
    assert first["evidence"] + second["evidence"] == evidence
    assert second["next_evidence_offset"] is None
    for tool, args in (
        ("get_machine", {"machine_id": str(foreign_machine.id)}),
        ("get_finding", {"finding_id": str(foreign_finding.finding_id)}),
        ("get_scan_machine", {
            "scan_id": str(foreign_scan.scan_id),
            "machine_id": str(foreign_machine.id),
        }),
    ):
        assert read_tool(mcp_client, token, tool, args)["isError"] is True


def test_protocol_revocation_and_resource_binding(
    mcp_client, member, monkeypatch,
):
    client_id, tokens, _ = connect(mcp_client, member)
    response = mcp_client.post("/revoke", data={
        "client_id": client_id, "token": tokens["refresh_token"],
    })
    assert response.status_code == 200, response.text
    assert mcp_auth.load_access_token(tokens["access_token"]) is None
    _, tokens, _ = connect(mcp_client, member)
    configured = mcp_auth.get_settings().model_copy(update={
        "mcp_public_url": "https://other.example/mcp",
    })
    monkeypatch.setattr(mcp_auth, "get_settings", lambda: configured)
    assert mcp_auth.load_access_token(tokens["access_token"]) is None


def test_mcp_tables_runtime_grants_and_supabase_isolation(runtime_session):
    for table in (
        "mcp_clients", "mcp_connections", "mcp_authorizations", "mcp_credentials",
    ):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert runtime_session.execute(text(
                "SELECT has_table_privilege('dmitri_runtime', :table, :privilege)"
            ), {"table": table, "privilege": privilege}).scalar_one()
        assert not runtime_session.execute(text(
            "SELECT has_table_privilege('anon', :table, 'SELECT')"
        ), {"table": table}).scalar_one()
        assert not runtime_session.execute(text(
            "SELECT has_table_privilege('authenticated', :table, 'SELECT')"
        ), {"table": table}).scalar_one()


def test_concurrent_refresh_detects_reuse(mcp_client, member):
    client_id, tokens, _ = connect(mcp_client, member)
    form = {
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [
            executor.submit(mcp_client.post, "/token", data=form)
            for _ in range(2)
        ]
        responses = [future.result(timeout=15) for future in requests]
    assert sorted(response.status_code for response in responses) == [200, 400]
    success = next(response for response in responses if response.status_code == 200)
    assert mcp_auth.load_access_token(success.json()["access_token"]) is None


def test_removed_user_loses_access(mcp_client, member, administrative_session):
    client_id, tokens, _ = connect(mcp_client, member)
    administrative_session.delete(member)
    administrative_session.commit()
    assert rpc(mcp_client, tokens["access_token"], "tools/list").status_code == 401
    response = mcp_client.post("/token", data={
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
    })
    assert response.status_code == 400


def test_local_callback_port_can_change_but_exchange_uri_cannot(
    mcp_client, member,
):
    client_id, _ = start_authorization(mcp_client)
    callback = "http://127.0.0.1:9182/callback"
    response = mcp_client.get("/authorize", params={
        "client_id": client_id, "redirect_uri": callback,
        "response_type": "code", "code_challenge": CHALLENGE,
        "code_challenge_method": "S256", "resource": RESOURCE,
        "scope": "dmitri:read", "state": "new-port",
    }, follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert "request" in query, response.headers["location"]
    response = mcp_client.post(
        "/api/v1/mcp/authorization", headers=web_headers(member), json={
            "request_token": query["request"][0], "approve": True,
        },
    )
    redirect = urlsplit(response.json()["redirect_url"])
    assert redirect.port == 9182
    form = {
        "grant_type": "authorization_code", "client_id": client_id,
        "code": parse_qs(redirect.query)["code"][0], "resource": RESOURCE,
        "code_verifier": VERIFIER, "redirect_uri": CALLBACK,
    }
    assert mcp_client.post("/token", data=form).status_code == 400
    form["redirect_uri"] = callback
    assert mcp_client.post("/token", data=form).status_code == 200


@pytest.mark.parametrize("url", [
    "http://api.example.com/mcp",
    "https://api.example.com/mcp?token=secret",
    "https://user:password@api.example.com/mcp",
    "https://api.example.com/mcp#fragment",
    "https://api.example.com:99999/mcp",
    "https://api.example.com/other/mcp",
])
def test_invalid_public_endpoint_configuration(url):
    values = get_settings().model_dump(by_alias=True)
    with pytest.raises(ValidationError):
        Settings.model_validate({**values, "MCP_PUBLIC_URL": url})


def test_public_endpoint_configuration_is_canonical():
    values = get_settings().model_dump(by_alias=True)
    settings = Settings.model_validate({
        **values, "MCP_PUBLIC_URL": "https://API.EXAMPLE.COM:443/mcp",
    })
    assert settings.mcp_public_url == "https://api.example.com/mcp"


def test_cached_client_can_reauthorize_after_connection_expiry(
    mcp_client, member, administrative_session,
):
    client_id, tokens, _ = connect(mcp_client, member)
    client = administrative_session.get(McpClient, client_id)
    client.created_at = utc_now() - timedelta(days=31)
    connection = administrative_session.exec(select(McpConnection)).one()
    connection.expires_at = utc_now() - timedelta(days=1)
    administrative_session.add_all([client, connection])
    administrative_session.commit()
    response = mcp_client.get("/authorize", params={
        "client_id": client_id, "redirect_uri": CALLBACK,
        "response_type": "code", "code_challenge": CHALLENGE,
        "code_challenge_method": "S256", "resource": RESOURCE,
        "scope": "dmitri:read",
    }, follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert "request" in query, response.headers["location"]
    decision = mcp_client.post(
        "/api/v1/mcp/authorization", headers=web_headers(member), json={
            "request_token": query["request"][0], "approve": True,
        },
    )
    assert decision.status_code == 200, decision.text
    assert mcp_auth.load_access_token(tokens["access_token"]) is None


def test_refresh_does_not_extend_connection_lifetime(
    mcp_client, member, administrative_session,
):
    client_id, tokens, _ = connect(mcp_client, member)
    connection = administrative_session.exec(select(McpConnection)).one()
    expiry = utc_now() + timedelta(seconds=30)
    connection.expires_at = expiry
    administrative_session.add(connection)
    administrative_session.commit()
    response = mcp_client.post("/token", data={
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
    })
    assert response.status_code == 200, response.text
    assert 0 < response.json()["expires_in"] <= 30
    credential = administrative_session.get(
        McpCredential, hash_token(response.json()["access_token"])
    )
    assert credential.expires_at == expiry
