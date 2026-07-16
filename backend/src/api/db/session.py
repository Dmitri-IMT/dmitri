from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlmodel import Session, create_engine

from api.core.config import get_settings

_POSTGRES_PREFIXES = (
    "postgres://",
    "postgresql://",
    "postgresql+psycopg://",
    "postgresql+asyncpg://",
)


def _normalize_database_url(database_url: str) -> str:
    if not database_url.startswith(_POSTGRES_PREFIXES):
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
    return "postgresql+psycopg://" + database_url.split("://", 1)[1]


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    database_url = _normalize_database_url(settings.database_url.get_secret_value())
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None, "connect_timeout": 10},
    )


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def reset_db_state() -> None:
    get_engine.cache_clear()
    get_settings.cache_clear()
