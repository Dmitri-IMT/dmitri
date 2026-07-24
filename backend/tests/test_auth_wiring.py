from __future__ import annotations

import pytest
from api.main import app
from starlette.testclient import TestClient

AUTH_POST_PATHS = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/change-password",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
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
