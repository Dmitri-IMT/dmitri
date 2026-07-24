from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.models import persistence
from api.models.identity import Org, User
from api.models.session import PasswordResetToken, RefreshToken
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]

SESSION_TABLES = ("refresh_tokens", "password_reset_tokens")


def _load_auth_migration():
    path = next((ROOT / "alembic/versions").glob("*_auth_sessions.py"))
    spec = importlib.util.spec_from_file_location("dmi60_auth_sessions", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _simulate_upgrade(module, monkeypatch: pytest.MonkeyPatch):
    metadata = sa.MetaData()
    created: dict[str, sa.Table] = {}
    indexes: list[tuple[str, str, list[object], bool]] = []
    executed: list[str] = []

    def create_table(name: str, *elements: object) -> None:
        created[name] = sa.Table(name, metadata, *elements)

    def create_index(
        name: str, table: str, columns: list[object], *, unique: bool = False
    ) -> None:
        indexes.append((name, table, columns, unique))

    def execute(sql: object) -> None:
        executed.append(" ".join(str(sql).split()))

    monkeypatch.setattr(module.op, "create_table", create_table)
    monkeypatch.setattr(module.op, "create_index", create_index)
    monkeypatch.setattr(module.op, "execute", execute)

    module.upgrade()
    return created, indexes, executed


def test_migration_creates_session_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_auth_migration()
    created, indexes, _ = _simulate_upgrade(module, monkeypatch)

    assert tuple(created) == SESSION_TABLES

    index_by_name = {name: (table, unique) for name, table, _, unique in indexes}
    assert index_by_name["ix_refresh_tokens_family_id"] == ("refresh_tokens", False)
    assert index_by_name["ix_refresh_tokens_token_hash"] == ("refresh_tokens", True)
    assert index_by_name["ix_password_reset_tokens_token_hash"] == (
        "password_reset_tokens",
        True,
    )

    refresh_fks = {
        fk.target_fullname for fk in created["refresh_tokens"].foreign_keys
    }
    assert refresh_fks == {"users.id"}
    reset_fks = {
        fk.target_fullname for fk in created["password_reset_tokens"].foreign_keys
    }
    assert reset_fks == {"users.id"}


def test_migration_extends_security_fence_without_sequences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_auth_migration()
    _, _, executed = _simulate_upgrade(module, monkeypatch)

    for table in SESSION_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in executed

    qualified = ", ".join(f"public.{table}" for table in SESSION_TABLES)
    assert (
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {qualified} TO dmitri_runtime"
        in executed
    )
    assert not any("SEQUENCE" in statement for statement in executed)
    assert not any(
        "DELETE" in statement and "dmitri_runtime" in statement
        for statement in executed
    )
    assert not any("CREATE ROLE" in statement for statement in executed)


def test_models_registered() -> None:
    tables = persistence.SQLModel.metadata.tables
    assert {"refresh_tokens", "password_reset_tokens"} <= set(tables)


def _seed_user(session: Session) -> User:
    org = Org(name="Acme")
    session.add(org)
    session.commit()
    session.refresh(org)
    user = User(
        org_id=org.id,
        email="alice@corp.com",
        password_hash="x",
        role="admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_refresh_token_hash_is_unique(administrative_session: Session) -> None:
    user = _seed_user(administrative_session)
    family_expires = datetime.now(timezone.utc) + timedelta(days=7)
    administrative_session.add(
        RefreshToken(
            user_id=user.id,
            family_id=uuid4(),
            token_hash="shared-hash",
            family_expires_at=family_expires,
        )
    )
    administrative_session.commit()

    administrative_session.add(
        RefreshToken(
            user_id=user.id,
            family_id=uuid4(),
            token_hash="shared-hash",
            family_expires_at=family_expires,
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_refresh_token_rejects_unknown_user(
    administrative_session: Session,
) -> None:
    administrative_session.add(
        RefreshToken(
            user_id=uuid4(),
            family_id=uuid4(),
            token_hash="orphan-hash",
            family_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_password_reset_token_hash_is_unique(
    administrative_session: Session,
) -> None:
    user = _seed_user(administrative_session)
    expires = datetime.now(timezone.utc) + timedelta(minutes=60)
    administrative_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash="shared-reset-hash",
            expires_at=expires,
        )
    )
    administrative_session.commit()

    administrative_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash="shared-reset-hash",
            expires_at=expires,
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_password_reset_token_rejects_unknown_user(
    administrative_session: Session,
) -> None:
    administrative_session.add(
        PasswordResetToken(
            user_id=uuid4(),
            token_hash="orphan-reset-hash",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()
