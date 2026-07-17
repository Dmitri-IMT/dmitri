from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlmodel import Session, create_engine

from api.core.config import get_settings, normalize_postgres_url


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    database_url = normalize_postgres_url(settings.database_url.get_secret_value())
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
