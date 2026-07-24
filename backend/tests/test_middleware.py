from __future__ import annotations

from api.core.config import Settings
from api.middleware import (
    REQUEST_ID_HEADER,
    NoContentCorsMiddleware,
    RequestIdMiddleware,
    build_cors_middleware_kwargs,
)
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def _ping(request):
    return PlainTextResponse("ok")


def _build_app() -> Starlette:
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://u:p@127.0.0.1:1/x",
        CORS_ALLOWED_ORIGINS="http://localhost:5173",
    )
    app = Starlette(routes=[Route("/ping", _ping)])
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        NoContentCorsMiddleware, **build_cors_middleware_kwargs(settings)
    )
    return app


def test_real_preflight_returns_204_with_cors_headers() -> None:
    client = TestClient(_build_app())
    response = client.options(
        "/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_inbound_request_id_is_echoed_back() -> None:
    client = TestClient(_build_app())
    response = client.get("/ping", headers={REQUEST_ID_HEADER: "req-123"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-123"


def test_missing_request_id_is_generated() -> None:
    client = TestClient(_build_app())
    response = client.get("/ping")

    assert response.status_code == 200
    generated = response.headers[REQUEST_ID_HEADER]
    assert generated
    assert len(generated) == 36
