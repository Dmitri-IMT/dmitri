from __future__ import annotations

from pathlib import Path

import pytest
from api.dependencies.auth import require_admin, require_user, require_user_row
from api.main import app
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_response_carries_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["x-request-id"]


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


def _dependency_calls(dependant) -> set:
    """Every dependency a route resolves, including nested ones.

    `require_admin_row` pairs the admin gate with the caller's row, so the gate
    is one level down from the route. Walking the tree keeps this a test of what
    guards the route rather than of how the dependency is spelled.
    """
    calls = set()
    for dep in dependant.dependencies:
        calls.add(dep.call)
        calls |= _dependency_calls(dep)
    return calls


DELETE_ROUTES = (
    ("/api/v1/users/me", require_user_row),
    ("/api/v1/users/{user_id}", require_admin),
)


@pytest.mark.parametrize("path,dependency", DELETE_ROUTES)
def test_user_delete_route_is_registered_with_its_dependency(path, dependency) -> None:
    route = next(
        r
        for r in _flatten_routes(app.routes)
        if getattr(r, "path", None) == path and "DELETE" in getattr(r, "methods", set())
    )
    calls = _dependency_calls(route.dependant)

    assert dependency in calls


ADMIN_ROUTES = (
    ("/api/v1/users", "GET"),
    ("/api/v1/users/{user_id}", "PATCH"),
    ("/api/v1/invites", "GET"),
    ("/api/v1/invites/{invite_id}", "DELETE"),
)


@pytest.mark.parametrize("path,method", ADMIN_ROUTES)
def test_admin_route_is_registered_with_unconditional_admin_dependency(
    path: str, method: str
) -> None:
    route = next(
        r
        for r in _flatten_routes(app.routes)
        if getattr(r, "path", None) == path and method in getattr(r, "methods", set())
    )
    calls = _dependency_calls(route.dependant)

    assert require_admin in calls


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
