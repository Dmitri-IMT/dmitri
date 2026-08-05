from __future__ import annotations

import importlib.metadata
import os

import pytest
from api.db.session import get_session
from api.main import app
from conftest import _dispose_runtime_engine
from fastapi.routing import APIRoute
from sqlmodel import Session
from starlette.testclient import TestClient


def _flatten_api_routes(routes: list) -> list[APIRoute]:
    flattened: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            flattened.append(route)
        elif hasattr(route, "original_router"):
            flattened.extend(_flatten_api_routes(route.original_router.routes))
    return flattened


DISCARDED_BUSINESS_PATHS = (
    "/scans",
    "/findings",
)

# Every (path, method) the app is allowed to expose. Adding a route without
# updating this set is a deliberate decision, not an accident.
EXPECTED_ROUTE_SURFACE = {
    ("/api/v1/health", "GET"),
    ("/api/v1/health", "OPTIONS"),
    ("/api/v1/hosts", "GET"),
    ("/api/v1/hosts/{host_id}", "GET"),
    ("/api/v1/scans", "GET"),
    ("/api/v1/scans", "POST"),
    ("/api/v1/scans/{scan_id}", "GET"),
    ("/api/v1/findings", "GET"),
} | {
    (f"/api/v1/auth/{name}", method)
    for name in (
        "login",
        "refresh",
        "logout",
        "change-password",
        "forgot-password",
        "reset-password",
    )
    for method in ("POST", "OPTIONS")
} | {
    ("/api/v1/invites", "POST"),
    ("/api/v1/invites", "OPTIONS"),
    ("/api/v1/invites/accept", "POST"),
    ("/api/v1/invites/accept", "OPTIONS"),
    ("/api/v1/users/me", "GET"),
    ("/api/v1/agents/{agent_id}/commands", "POST"),
    ("/api/v1/agents/{agent_id}/commands", "OPTIONS"),
    ("/api/v1/commands/{command_id}", "GET"),
    ("/api/v1/commands/{command_id}", "OPTIONS"),
}


def test_health_ok_after_live_db_round_trip(runtime_session: Session) -> None:
    def _override_get_session():
        yield runtime_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        client = TestClient(app)
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": app.version}
    assert app.version == importlib.metadata.version("backend-api") == "0.1.0"


def test_health_returns_503_when_database_unreachable() -> None:
    previous_database_url = os.environ.get("DATABASE_URL")
    _dispose_runtime_engine()
    os.environ["DATABASE_URL"] = "postgresql+psycopg://u:p@127.0.0.1:1/x"

    client = TestClient(app)
    response = client.get("/api/v1/health")

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
    assert "127.0.0.1" not in response.text
    assert "psycopg" not in response.text
    assert "u:p" not in response.text


def test_route_surface_exposes_only_canonical_health() -> None:
    client = TestClient(app)

    for path in ("/", "/docs", "/redoc", "/openapi.json") + DISCARDED_BUSINESS_PATHS:
        assert client.get(path).status_code == 404

    assert client.options("/api/v1/health").status_code == 204


def test_route_surface_is_exactly_the_declared_contract() -> None:
    surface = {
        (route.path, method)
        for route in _flatten_api_routes(app.routes)
        for method in route.methods
    }

    assert surface == EXPECTED_ROUTE_SURFACE


def test_app_registers_lifespan_not_startup_hooks() -> None:
    assert app.router.on_startup == []
    assert app.router.on_shutdown == []
    assert app.router.lifespan_context is not None


def test_smoke_test_module_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("api.smoke_test")


def test_routers_package_is_importable() -> None:
    importlib.import_module("api.routers")
