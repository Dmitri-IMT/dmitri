from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from api.main import app
from api.models.identity import Org
from api.models.persistence import HostRecord
from conftest import _dispose_runtime_engine
from pydantic import BaseModel
from sqlmodel import Session
from starlette.testclient import TestClient


class _NestedHost(BaseModel):
    ip: str


class _NestedBody(BaseModel):
    hosts: list[_NestedHost]


def _assert_error_envelope(
    response, status_code: int, code: str, details: dict | None = None
) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert "detail" not in body
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["details"] == (details or {})


def _seed_host(session: Session) -> tuple[Org, HostRecord]:
    now = datetime.now(timezone.utc)
    org = Org(name="Org A")
    session.add(org)
    session.flush()
    host = HostRecord(
        identity_key="aa:bb:cc:dd:ee:ff",
        org_id=org.id,
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        hostname="host-a",
        vendor="Acme",
        open_ports_count=0,
        highest_severity="none",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(host)
    session.flush()
    return org, host


def test_hosts_without_bearer_returns_unauthorized_envelope(
    client: TestClient, administrative_session: Session
) -> None:
    _seed_host(administrative_session)
    response = client.get("/api/v1/hosts")
    _assert_error_envelope(response, 401, "unauthorized")


def test_viewer_post_invite_returns_forbidden_envelope(
    client: TestClient, seeded_org: Org, bearer_headers
) -> None:
    response = client.post(
        "/api/v1/invites",
        json={"email": "new@corp.com", "role": "viewer"},
        headers=bearer_headers(seeded_org.id, "viewer"),
    )
    _assert_error_envelope(response, 403, "forbidden")


def test_unknown_host_returns_not_found_envelope(
    client: TestClient, administrative_session: Session, bearer_headers
) -> None:
    org, _ = _seed_host(administrative_session)
    response = client.get(
        f"/api/v1/hosts/{uuid4()}",
        headers=bearer_headers(org.id, "admin"),
    )
    _assert_error_envelope(response, 404, "not_found")


def test_unmatched_path_returns_not_found_envelope() -> None:
    response = TestClient(app).get("/api/v1/nope")
    _assert_error_envelope(response, 404, "not_found")


def test_wrong_method_returns_method_not_allowed_envelope() -> None:
    response = TestClient(app).post("/api/v1/hosts")
    _assert_error_envelope(response, 405, "method_not_allowed")
    # RFC 9110 requires Allow on a 405. Starlette's router sets it via
    # HTTPException.headers, which the envelope handler must pass through.
    assert response.headers["allow"] == "GET"


def test_validation_failure_returns_validation_error_envelope() -> None:
    response = TestClient(app).post(
        "/api/v1/auth/reset-password",
        json={"token": "t", "new_password": "short"},
    )
    _assert_error_envelope(
        response, 422, "validation_error", {"field": "new_password"}
    )


def test_validation_failure_does_not_echo_submitted_password() -> None:
    weak_password = "hunter7"

    response = TestClient(app).post(
        "/api/v1/auth/reset-password",
        json={"token": "t", "new_password": weak_password},
    )

    assert response.status_code == 422
    assert weak_password not in response.text


def test_validation_error_details_carry_nested_field_path() -> None:
    @app.post("/__test_nested_validation__")
    def _nested(body: _NestedBody) -> None: ...

    try:
        response = TestClient(app).post(
            "/__test_nested_validation__",
            json={"hosts": [{"ip": 5}]},
        )
    finally:
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__test_nested_validation__"
        ]

    _assert_error_envelope(
        response, 422, "validation_error", {"field": "hosts[0].ip"}
    )


def test_health_database_failure_returns_existing_envelope() -> None:
    previous_database_url = os.environ.get("DATABASE_URL")
    _dispose_runtime_engine()
    os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@127.0.0.1:1/x"

    response = TestClient(app).get("/api/v1/health")

    _dispose_runtime_engine()
    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unreachable",
            "message": "Database connection failed.",
            "details": {},
        }
    }


def test_unhandled_exception_returns_internal_server_error_envelope() -> None:
    @app.get("/__test_internal_error__")
    def _raise_runtime_error() -> None:
        raise RuntimeError("boom")

    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/__test_internal_error__"
        )
    finally:
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__test_internal_error__"
        ]

    _assert_error_envelope(response, 500, "internal_server_error")
    assert "boom" not in response.text
