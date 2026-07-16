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

DISCARDED_BUSINESS_PATHS = (
    "/scans",
    "/api/v1/scans",
    "/findings",
    "/api/v1/findings",
)


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

    assert client.options("/api/v1/health").status_code == 405

    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert [route.path for route in api_routes] == ["/api/v1/health"]
    assert api_routes[0].methods == {"GET"}


def test_app_has_no_lifespan_hook_or_middleware() -> None:
    assert app.user_middleware == []
    assert app.router.on_startup == []
    assert app.router.on_shutdown == []


def test_smoke_test_module_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("api.smoke_test")


def test_routers_package_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("api.routers")
