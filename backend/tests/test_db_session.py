from __future__ import annotations

import pytest
import sqlalchemy as sa
from api.db import session as session_module
from api.db.session import get_engine, get_session, reset_db_state
from api.models import persistence as persistence_module
from pydantic import ValidationError
from sqlmodel import Session


@pytest.mark.parametrize(
    "prefix",
    [
        "postgres://",
        "postgresql://",
        "postgresql+psycopg://",
        "postgresql+asyncpg://",
    ],
)
def test_get_engine_normalizes_accepted_urls_with_pooler_safe_args(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"{prefix}user:pass@host/db")
    reset_db_state()
    captured: dict[str, object] = {}

    def _fake_create_engine(url: str, **kwargs: object) -> object:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(session_module, "create_engine", _fake_create_engine)

    get_engine()

    assert captured["url"] == "postgresql+psycopg://user:pass@host/db"
    kwargs = captured["kwargs"]
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["connect_args"]["prepare_threshold"] is None
    assert kwargs["connect_args"]["connect_timeout"] == 10
    reset_db_state()


@pytest.mark.parametrize("url", ["sqlite:///x.db", "mysql://user:pass@host/db"])
def test_normalize_database_url_rejects_non_postgres(url: str) -> None:
    with pytest.raises(ValueError):
        session_module._normalize_database_url(url)


def test_non_postgres_url_never_reaches_create_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session_module,
        "create_engine",
        lambda *args, **kwargs: pytest.fail("create_engine was called"),
    )

    with pytest.raises(ValueError):
        session_module._normalize_database_url("mongodb://host/db")


def test_settings_rejects_non_postgres_before_engine_module_is_touched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./scanner.db")

    with pytest.raises(ValidationError):
        from api.core.config import Settings

        Settings()


def test_no_init_db_attribute() -> None:
    assert not hasattr(session_module, "init_db")


def test_no_schema_creation_imports_in_session_module() -> None:
    assert not hasattr(session_module, "SQLModel")
    assert not hasattr(session_module, "create_all")


def test_sqlmodel_metadata_anchor_is_absent() -> None:
    assert not hasattr(persistence_module, "SQLModelMetadataAnchor")


def test_reset_db_state_clears_cached_engine_and_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://first:pass@hostone/db")
    reset_db_state()
    captured_urls: list[str] = []

    def _fake_create_engine(url: str, **kwargs: object) -> object:
        captured_urls.append(url)
        return object()

    monkeypatch.setattr(session_module, "create_engine", _fake_create_engine)

    get_engine()
    assert captured_urls == ["postgresql+psycopg://first:pass@hostone/db"]

    monkeypatch.setenv("DATABASE_URL", "postgresql://second:pass@hosttwo/db")
    get_engine()
    assert captured_urls == ["postgresql+psycopg://first:pass@hostone/db"]

    reset_db_state()
    get_engine()
    assert captured_urls == [
        "postgresql+psycopg://first:pass@hostone/db",
        "postgresql+psycopg://second:pass@hosttwo/db",
    ]
    reset_db_state()


def test_get_session_yields_session_bound_to_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = sa.create_engine("sqlite://")
    monkeypatch.setattr(session_module, "get_engine", lambda: engine)

    generator = get_session()
    db_session = next(generator)

    assert isinstance(db_session, Session)
    assert db_session.bind is engine

    with pytest.raises(StopIteration):
        next(generator)
