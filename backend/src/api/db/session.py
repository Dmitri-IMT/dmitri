from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from api.core.config import get_settings


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return database_url


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    database_url = _normalize_database_url(settings.database_url)
    return create_engine(
        database_url,
        echo=False,
        connect_args=_connect_args(database_url),
    )


def init_db() -> None:
    from api.models.persistence import SQLModelMetadataAnchor  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def reset_db_state() -> None:
    get_engine.cache_clear()
    get_settings.cache_clear()
