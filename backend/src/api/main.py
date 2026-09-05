from __future__ import annotations

import importlib.metadata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from api.core.config import get_settings
from api.db.session import get_engine, get_session
from api.errors import (
    DEFAULT_CODES_BY_STATUS,
    ApiError,
    error_envelope,
    field_path,
)
from api.middleware import (
    NoContentCorsMiddleware,
    RequestIdMiddleware,
    build_cors_middleware_kwargs,
)
from api.routers import (
    agents,
    auth,
    commands,
    findings,
    home,
    hosts,
    invites,
    scans,
    users,
)
from api.services.agent_presence import reconcile_all

APP_VERSION = importlib.metadata.version("backend-api")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # The connection registry is process-local, so no agent is connected yet on
    # a fresh process: clear stale connected_at rows a previous crash left set.
    with Session(get_engine()) as session:
        reconcile_all(session)
    yield


app = FastAPI(
    title="Dmitri Backend",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(NoContentCorsMiddleware, **build_cors_middleware_kwargs(settings))
app.add_middleware(RequestIdMiddleware)


# Also serves WebSocket routes: an HTTPException raised while solving a WS dependency
# (see `require_agent_ws`) reaches this handler with a WebSocket, not a Request, as the
# first argument — hence the widened annotation. Only `exc` is read either way.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request | WebSocket, exc: StarletteHTTPException
) -> JSONResponse:
    code = (
        exc.code
        if isinstance(exc, ApiError)
        else DEFAULT_CODES_BY_STATUS.get(exc.status_code, "error")
    )
    message = str(exc.detail) if exc.detail else code
    # Starlette's router raises 405 with an `Allow` header (RFC 9110 requires it), and
    # FastAPI's default handler propagated `exc.headers`. Dropping them here would
    # silently strip that header — and any future WWW-Authenticate / Retry-After.
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(code, message),
        headers=getattr(exc, "headers", None),
    )


# The body is fixed on purpose: pydantic's `errors()` carries `input` (the rejected
# value verbatim) and `ctx`, so echoing them would leak the submitted password on the
# min-length rejection for change-password / reset-password. For the same reason the raw
# errors are not logged either — the log file is not a safer place for a plaintext
# password than the response body.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    path = field_path(errors[0]["loc"]) if errors else ""
    return JSONResponse(
        status_code=422,
        content=error_envelope(
            "validation_error",
            "Request body validation failed.",
            {"field": path} if path else None,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_envelope("internal_server_error", "Internal server error."),
    )


# A malformed path param on a WS route fails during dependency solving, so no auth
# dependency runs. FastAPI's default is close(1008); openapi.yaml publishes 403 for a
# non-UUID {agent_id}, so deny explicitly instead of relying on the ASGI server to
# render the pre-accept close as 403. Requires the `websocket.http.response`
# extension (uvicorn's websockets impls advertise it). RFC 6455's 123-byte limit
# applies to the WebSocket close reason, not this HTTP denial body — but the message
# stays fixed anyway: this denial is unauthenticated, so it says nothing about the
# request beyond the status.
@app.exception_handler(WebSocketRequestValidationError)
async def ws_validation_denial(
    websocket: WebSocket, exc: WebSocketRequestValidationError
) -> None:
    await websocket.send_denial_response(
        JSONResponse(
            status_code=403,
            content=error_envelope("forbidden", "Invalid agent id."),
        )
    )


@app.get("/api/v1/health")
def read_health(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                "database_unreachable", "Database connection failed."
            ),
        )
    return {"status": "ok", "version": app.version}


@app.options("/api/v1/health", status_code=204)
def options_health() -> None:
    return None


app.include_router(agents.router)
app.include_router(commands.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(hosts.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(home.router)
app.include_router(invites.router)
