from __future__ import annotations

import importlib.metadata

from fastapi import Depends, FastAPI, WebSocket
from fastapi.exceptions import WebSocketRequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from starlette.responses import Response

from api.core.config import get_settings
from api.db.session import get_session
from api.middleware import (
    NoContentCorsMiddleware,
    RequestIdMiddleware,
    build_cors_middleware_kwargs,
)
from api.routers import agents, auth, findings, hosts, invites, scans

APP_VERSION = importlib.metadata.version("backend-api")

settings = get_settings()

app = FastAPI(
    title="Dmitri Backend",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(NoContentCorsMiddleware, **build_cors_middleware_kwargs(settings))
app.add_middleware(RequestIdMiddleware)


# A malformed path param on a WS route fails during dependency solving, so no auth
# dependency runs. FastAPI's default is close(1008); openapi.yaml publishes 403 for a
# non-UUID {agent_id}, so deny explicitly instead of relying on the ASGI server to
# render the pre-accept close as 403. Requires the `websocket.http.response`
# extension (uvicorn's websockets impls advertise it); the pydantic detail is dropped
# on purpose — it exceeds RFC 6455's 123-byte close reason.
@app.exception_handler(WebSocketRequestValidationError)
async def ws_validation_denial(
    websocket: WebSocket, exc: WebSocketRequestValidationError
) -> None:
    await websocket.send_denial_response(Response(status_code=403))


@app.get("/api/v1/health")
def read_health(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unreachable",
                    "message": "Database connection failed.",
                    "details": {},
                }
            },
        )
    return {"status": "ok", "version": app.version}


@app.options("/api/v1/health", status_code=204)
def options_health() -> None:
    return None


app.include_router(agents.router)
app.include_router(auth.router)
app.include_router(hosts.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(invites.router)
