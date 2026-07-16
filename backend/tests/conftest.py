from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine, make_url
from sqlmodel import Session, SQLModel

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")
RUNTIME_URL = DATABASE_URL_TEST or "postgresql+psycopg://u:p@127.0.0.1:1/x"
os.environ["DATABASE_URL"] = RUNTIME_URL
if DATABASE_URL_TEST is not None:
    os.environ["DATABASE_URL_DIRECT"] = DATABASE_URL_TEST

from api.db.session import get_engine, reset_db_state  # noqa: E402
from api.models import persistence  # noqa: E402, F401

EXPECTED_DATABASE = "dmitri_test"
SUPABASE_API_ROLES = ("anon", "authenticated")


def _psycopg_url(database_url: str) -> str:
    url = make_url(database_url)
    return url.set(drivername="postgresql+psycopg").render_as_string(
        hide_password=False
    )


def _assert_test_database(database_url: str, connection: Connection) -> None:
    if make_url(database_url).database != EXPECTED_DATABASE:
        raise RuntimeError("DATABASE_URL_TEST must target the dmitri_test database.")
    database = connection.execute(sa.text("SELECT current_database()"))
    if database.scalar_one() != EXPECTED_DATABASE:
        raise RuntimeError("Connected database must be dmitri_test.")


def _alembic_config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def _dispose_runtime_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    reset_db_state()


def _migrate(engine: Engine, revision: str) -> None:
    assert DATABASE_URL_TEST is not None
    with engine.connect() as connection:
        _assert_test_database(DATABASE_URL_TEST, connection)
    if revision == "base":
        command.downgrade(_alembic_config(), "base")
    else:
        command.upgrade(_alembic_config(), revision)
        with engine.begin() as connection:
            _assert_test_database(DATABASE_URL_TEST, connection)
            connection.execute(
                sa.text(
                    "DO $$ BEGIN EXECUTE format("
                    "'GRANT dmitri_runtime TO %I', current_user); END $$"
                )
            )


def _truncate_application_tables(engine: Engine) -> None:
    assert DATABASE_URL_TEST is not None
    tables = ", ".join(
        f'public."{table.name}"' for table in SQLModel.metadata.sorted_tables
    )
    with engine.begin() as connection:
        _assert_test_database(DATABASE_URL_TEST, connection)
        connection.execute(sa.text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    if DATABASE_URL_TEST is None:
        pytest.skip("DATABASE_URL_TEST not set")
    engine = sa.create_engine(_psycopg_url(DATABASE_URL_TEST))
    created_roles: list[str] = []
    with engine.begin() as connection:
        _assert_test_database(DATABASE_URL_TEST, connection)
        existing_roles = set(
            connection.execute(
                sa.text(
                    "SELECT rolname FROM pg_roles "
                    "WHERE rolname IN ('anon', 'authenticated')"
                )
            ).scalars()
        )
        for role in SUPABASE_API_ROLES:
            if role not in existing_roles:
                connection.execute(sa.text(f"CREATE ROLE {role} NOLOGIN"))
                created_roles.append(role)
    try:
        _dispose_runtime_engine()
        _migrate(engine, "head")
        yield engine
    finally:
        _migrate(engine, "base")
        with engine.begin() as connection:
            _assert_test_database(DATABASE_URL_TEST, connection)
            for role in created_roles:
                connection.execute(sa.text(f"DROP ROLE {role}"))
        engine.dispose()
        _dispose_runtime_engine()


@pytest.fixture
def migrated_database(postgres_engine: Engine) -> Engine:
    _truncate_application_tables(postgres_engine)
    return postgres_engine


@pytest.fixture
def administrative_session(
    migrated_database: Engine,
) -> Generator[Session, None, None]:
    with Session(migrated_database) as session:
        yield session


@pytest.fixture
def runtime_session(migrated_database: Engine) -> Generator[Session, None, None]:
    assert DATABASE_URL_TEST is not None
    with migrated_database.connect() as connection:
        _assert_test_database(DATABASE_URL_TEST, connection)
        connection.execute(sa.text("SET ROLE dmitri_runtime"))
        connection.commit()
        assert connection.execute(sa.text("SELECT current_user")).scalar_one() == (
            "dmitri_runtime"
        )
        connection.commit()
        with Session(bind=connection) as session:
            yield session
        connection.execute(sa.text("RESET ROLE"))
        connection.commit()
