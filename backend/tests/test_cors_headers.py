from __future__ import annotations

from api.main import app
from api.middleware import REQUEST_ID_HEADER
from starlette.testclient import TestClient

ALLOWED_ORIGIN = "http://localhost:5173"


def test_real_preflight_returns_204_with_cors_headers() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    allow_methods = response.headers["access-control-allow-methods"]
    assert "GET" in allow_methods
    assert "POST" in allow_methods
    assert "OPTIONS" in allow_methods
    allow_headers = response.headers["access-control-allow-headers"]
    assert "authorization" in allow_headers.lower()
    assert "content-type" in allow_headers.lower()
    assert REQUEST_ID_HEADER.lower() in allow_headers.lower()


def test_inbound_request_id_is_echoed_back() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            REQUEST_ID_HEADER: "req-123",
        },
    )

    assert response.headers[REQUEST_ID_HEADER] == "req-123"


def test_missing_request_id_is_generated() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    generated = response.headers[REQUEST_ID_HEADER]
    assert generated
    assert len(generated) == 36
