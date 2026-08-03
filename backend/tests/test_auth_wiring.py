from __future__ import annotations

from pathlib import Path

import pytest
from api.dependencies.auth import require_user
from api.main import app
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient

AUTH_POST_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/change-password",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
)

INVITE_POST_PATHS = (
    "/api/v1/invites",
    "/api/v1/invites/accept",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("path", AUTH_POST_PATHS)
def test_auth_post_paths_are_registered(client: TestClient, path: str) -> None:
    response = client.post(path, json={})

    assert response.status_code not in (404, 405)


def test_options_health_returns_204(client: TestClient) -> None:
    response = client.options("/api/v1/health")

    assert response.status_code == 204


def test_auth_preflight_returns_204_with_cors_headers(client: TestClient) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.parametrize("path", AUTH_POST_PATHS)
def test_response_carries_request_id_header(client: TestClient, path: str) -> None:
    response = client.post(path, json={})

    assert response.headers["x-request-id"]


def test_health_response_carries_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["x-request-id"]


@pytest.mark.parametrize("path", INVITE_POST_PATHS)
def test_invite_post_paths_are_registered(client: TestClient, path: str) -> None:
    response = client.post(path, json={})

    assert response.status_code not in (404, 405)


@pytest.mark.parametrize("path", INVITE_POST_PATHS)
def test_invite_preflight_returns_204(client: TestClient, path: str) -> None:
    response = client.options(
        path,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 204


def _flatten_routes(routes):
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from _flatten_routes(nested.routes)
        else:
            yield route


def test_agent_commands_websocket_route_is_registered() -> None:
    websocket_paths = {
        route.path
        for route in _flatten_routes(app.routes)
        if isinstance(route, WebSocketRoute)
    }

    assert "/api/v1/agents/{agent_id}/commands" in websocket_paths


def test_invite_routes_and_preflights_appear_in_app_routes() -> None:
    registered = {
        (route.path, method)
        for route in _flatten_routes(app.routes)
        for method in getattr(route, "methods", set())
    }

    assert ("/api/v1/invites", "POST") in registered
    assert ("/api/v1/invites", "OPTIONS") in registered
    assert ("/api/v1/invites/accept", "POST") in registered
    assert ("/api/v1/invites/accept", "OPTIONS") in registered


READ_ROUTES = (
    ("/api/v1/hosts", "GET"),
    ("/api/v1/hosts/{host_id}", "GET"),
    ("/api/v1/scans/{scan_id}", "GET"),
    ("/api/v1/findings", "GET"),
)


@pytest.mark.parametrize("path,method", READ_ROUTES)
def test_read_route_depends_on_require_user(path: str, method: str) -> None:
    route = next(
        r
        for r in _flatten_routes(app.routes)
        if getattr(r, "path", None) == path and method in getattr(r, "methods", set())
    )
    calls = {dep.call for dep in route.dependant.dependencies}

    assert require_user in calls


def test_no_placeholder_org_id_remains() -> None:
    root = Path(__file__).resolve().parents[1]
    this_file = Path(__file__).resolve()
    forbidden = ("_PLACEHOLDER_ORG_ID", "00000000-0000-0000-0000-000000000000")

    for base in (root / "src", root / "tests"):
        for path in base.rglob("*.py"):
            if path.resolve() == this_file:
                continue
            text = path.read_text()
            for token in forbidden:
                assert token not in text, f"{path} contains {token}"
