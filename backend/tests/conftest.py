from __future__ import annotations

import os
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy.engine import Connection, Engine, make_url
from sqlmodel import Session, SQLModel
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")
RUNTIME_URL = DATABASE_URL_TEST or "postgresql+psycopg://u:p@127.0.0.1:1/x"
os.environ["DATABASE_URL"] = RUNTIME_URL
os.environ.setdefault("JWT_SIGNING_SECRET", "test-jwt-signing-secret")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
if DATABASE_URL_TEST is not None:
    os.environ["DATABASE_URL_DIRECT"] = DATABASE_URL_TEST

from api.core.config import Settings  # noqa: E402
from api.db.session import get_engine, get_session, reset_db_state  # noqa: E402
from api.main import app  # noqa: E402
from api.models import persistence  # noqa: E402, F401
from api.models.command import Agent  # noqa: E402
from api.models.identity import Org, User  # noqa: E402
from api.models.persistence import utc_now  # noqa: E402
from api.services import agent_connections, device_sig  # noqa: E402
from api.services.passwords import hash_password  # noqa: E402
from api.services.tokens import create_access_token  # noqa: E402

# A developer's local backend/.env must not leak into the suite. CI has no such file, so
# reading it makes local runs disagree with CI: tests that explicitly unset DATABASE_URL
# or NVD_API_KEY still see values, and their assertions fail for environmental reasons.
Settings.model_config["env_file"] = None

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
        config = _alembic_config()
        script = ScriptDirectory.from_config(config)
        # The revision graph has a merge point, so a test that steps back to one
        # parent leaves two rows in `alembic_version`; read every current head.
        with engine.connect() as connection:
            current_heads = MigrationContext.configure(connection).get_current_heads()
        ancestors = (
            {
                rev.revision
                for head in current_heads
                for rev in script.iterate_revisions(head, None)
            }
            if current_heads
            else set()
        )
        if revision in ancestors and revision not in current_heads:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)
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


def pytest_configure(config: pytest.Config) -> None:
    if DATABASE_URL_TEST is None:
        raise pytest.UsageError(
            "DATABASE_URL_TEST must point at the dmitri_test database. "
            "Run ./database.sh --test."
        )


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    assert DATABASE_URL_TEST is not None
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
        _truncate_application_tables(engine)
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


@pytest.fixture
def seeded_org(administrative_session: Session) -> Org:
    org = Org(name="Test Org")
    administrative_session.add(org)
    administrative_session.commit()
    administrative_session.refresh(org)
    return org


@pytest.fixture
def client(administrative_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose requests run on the migrated Postgres test database.

    Route tests must exercise the real dialect: the read layer casts to INET and
    the schema leans on Postgres-only features (RLS, partial and expression
    indexes, ``postgresql_nulls_not_distinct``). A SQLite stand-in silently
    compiles none of that.
    """

    def _override_get_session() -> Generator[Session, None, None]:
        yield administrative_session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def actor_headers(
    administrative_session: Session,
) -> Callable[[UUID, str], dict[str, str]]:
    """Bearer headers whose subject is a real `User` row.

    Admin mutations denormalise the actor's email into the activity log, so the
    caller has to exist. A token for a subject with no row is a dead session and
    `require_user_row` answers 401 — use this instead of `bearer_headers`
    wherever the route reads the caller's own record.
    """

    def _actor_headers(org_id: UUID, role: str) -> dict[str, str]:
        actor = User(
            org_id=org_id,
            email=f"actor-{uuid4().hex[:12]}@corp.com",
            password_hash=hash_password("Xk9$mQvL2pTz"),
            role=role,
        )
        administrative_session.add(actor)
        administrative_session.commit()
        administrative_session.refresh(actor)
        token = create_access_token(user_id=actor.id, org_id=org_id, role=role)
        return {"Authorization": f"Bearer {token}"}

    return _actor_headers


@pytest.fixture
def bearer_headers() -> Callable[[UUID, str], dict[str, str]]:
    def _bearer_headers(org_id: UUID, role: str) -> dict[str, str]:
        token = create_access_token(user_id=uuid4(), org_id=org_id, role=role)
        return {"Authorization": f"Bearer {token}"}

    return _bearer_headers


def ws_upgrade_headers(
    private_key: bytes, agent_id: UUID, *, path: str | None = None
) -> dict[str, str]:
    resolved_path = path or f"/api/v1/agents/{agent_id}/commands"
    timestamp_str = utc_now().isoformat()
    nonce_value = uuid4().hex
    body_hash = device_sig.body_sha256(b"")
    canonical = device_sig.canonical_string(
        "GET", resolved_path, str(agent_id), timestamp_str, nonce_value, body_hash
    )
    signature = device_sig.sign(private_key, canonical)
    return {
        "X-Device-Id": str(agent_id),
        "X-Timestamp": timestamp_str,
        "X-Nonce": nonce_value,
        "X-Body-SHA256": body_hash,
        "X-Signature": signature,
    }


@pytest.fixture(autouse=True)
def clear_agent_connections_registry() -> Generator[None, None, None]:
    agent_connections._registry.clear()
    yield
    agent_connections._registry.clear()


@pytest.fixture
def sent_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., list[httpx.Request]]:
    """Configure a real ResendMailer behind a mock transport.

    Route-level callers get the production path -- get_mailer() builds a
    backgrounded ResendMailer because the key is set -- with the provider's
    HTTP call captured instead of made. Returns the list the requests land
    in; TestClient drains background tasks before returning, so a request
    that sent mail has already filled it by the time the test asserts. Pass
    ``fail=True`` to simulate a provider outage, ``status=`` to make the
    provider reject the message, and any Settings field as a keyword to
    override it. Settings are layered onto whatever ``mailer.get_settings``
    already returns, so a test module that pins its own values keeps them.
    """

    def _install(
        *, fail: bool = False, status: int = 200, **overrides: object
    ) -> list[httpx.Request]:
        from api.services import mailer

        configured = mailer.get_settings().model_copy(
            update={"resend_api_key": SecretStr("re_test_key"), **overrides}
        )
        monkeypatch.setattr(mailer, "get_settings", lambda: configured)

        captured: list[httpx.Request] = []
        real_client = httpx.Client

        def _handle(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            if fail:
                raise httpx.ConnectError("provider down", request=request)
            return httpx.Response(status, json={"id": "1"})

        def _client(**kwargs: object) -> httpx.Client:
            kwargs.pop("transport", None)
            return real_client(transport=httpx.MockTransport(_handle), **kwargs)

        monkeypatch.setattr(mailer.httpx, "Client", _client)
        return captured

    return _install


@pytest.fixture
def agent_keypair() -> tuple[bytes, bytes]:
    return device_sig.generate_keypair()


@pytest.fixture
def provisioned_agent(
    administrative_session: Session,
    seeded_org: Org,
    agent_keypair: tuple[bytes, bytes],
) -> Agent:
    _private_key, public_key = agent_keypair
    agent = Agent(
        org_id=seeded_org.id, display_name="Test Agent", public_key=public_key
    )
    administrative_session.add(agent)
    administrative_session.commit()
    administrative_session.refresh(agent)
    return agent
