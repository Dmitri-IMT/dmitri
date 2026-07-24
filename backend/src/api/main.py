from __future__ import annotations

import importlib.metadata

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from api.core.config import get_settings
from api.db.session import get_session
from api.middleware import (
    NoContentCorsMiddleware,
    RequestIdMiddleware,
    build_cors_middleware_kwargs,
)
from api.routers import auth, findings, hosts, scans

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


app.include_router(auth.router)
app.include_router(hosts.router)
app.include_router(scans.router)
app.include_router(findings.router)
