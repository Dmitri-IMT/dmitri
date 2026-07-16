from __future__ import annotations

import importlib.metadata

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from api.core.config import get_settings
from api.db.session import get_session

APP_VERSION = importlib.metadata.version("backend-api")

get_settings()

app = FastAPI(
    title="Dmitri Backend",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


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
