from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path

import sqlalchemy as sa
from api.models.identity import Org, User
from api.models.persistence import utc_now
from api.models.session import RefreshToken
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260808_15_user_delete_cascade.py"
    spec = importlib.util.spec_from_file_location("task_1_user_delete_cascade", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_op(migration, monkeypatch):
    dropped: list[tuple[str, str]] = []
    created: list[tuple[str, str, str, list[str], list[str], str | None]] = []
    executed: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, type_=None: dropped.append((name, table)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_foreign_key",
        lambda name, table, referent, local_cols, remote_cols, *, ondelete=None: (
            created.append((name, table, referent, local_cols, remote_cols, ondelete))
        ),
    )
    monkeypatch.setattr(migration.op, "execute", lambda sql: executed.append(sql))
    return dropped, created, executed


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260808_15"
    assert migration.down_revision == "20260804_14"


def test_migration_upgrade_recreates_foreign_keys_as_cascade(monkeypatch) -> None:
    migration = _load_migration()
    dropped, created, executed = _record_op(migration, monkeypatch)

    migration.upgrade()

    assert dropped == [
        ("refresh_tokens_user_id_fkey", "refresh_tokens"),
        ("password_reset_tokens_user_id_fkey", "password_reset_tokens"),
    ]
    assert created == [
        (
            "refresh_tokens_user_id_fkey",
            "refresh_tokens",
            "users",
            ["user_id"],
            ["id"],
            "CASCADE",
        ),
        (
            "password_reset_tokens_user_id_fkey",
            "password_reset_tokens",
            "users",
            ["user_id"],
            ["id"],
            "CASCADE",
        ),
    ]
    assert len(executed) == 1
    assert "GRANT DELETE" in executed[0]
    assert "public.users" in executed[0]
    assert "dmitri_runtime" in executed[0]


def test_migration_downgrade_restores_plain_foreign_keys(monkeypatch) -> None:
    migration = _load_migration()
    dropped, created, executed = _record_op(migration, monkeypatch)

    migration.downgrade()

    assert dropped == [
        ("refresh_tokens_user_id_fkey", "refresh_tokens"),
        ("password_reset_tokens_user_id_fkey", "password_reset_tokens"),
    ]
    assert [name for name, *_ in created] == [
        "refresh_tokens_user_id_fkey",
        "password_reset_tokens_user_id_fkey",
    ]
    assert all(entry[-1] is None for entry in created)
    assert len(executed) == 1
    assert "REVOKE DELETE" in executed[0]
    assert "public.users" in executed[0]
    assert "dmitri_runtime" in executed[0]


def test_live_foreign_keys_are_cascade_at_head(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT conname, confdeltype FROM pg_constraint "
                "WHERE contype = 'f' AND conname IN "
                "('refresh_tokens_user_id_fkey', "
                "'password_reset_tokens_user_id_fkey')"
            )
        ).all()

    assert dict(rows) == {
        "refresh_tokens_user_id_fkey": "c",
        "password_reset_tokens_user_id_fkey": "c",
    }


def test_runtime_role_deletes_user_and_cascades_refresh_token(
    administrative_session: Session, runtime_session: Session
) -> None:
    org = Org(name="Cascade Org")
    administrative_session.add(org)
    administrative_session.commit()
    administrative_session.refresh(org)

    user = User(
        org_id=org.id,
        email="cascade@corp.com",
        password_hash="x",
        role="admin",
    )
    administrative_session.add(user)
    administrative_session.commit()
    administrative_session.refresh(user)

    token = RefreshToken(
        user_id=user.id,
        family_id=user.id,
        token_hash="cascade-token-hash",
        family_expires_at=utc_now() + timedelta(days=1),
    )
    administrative_session.add(token)
    administrative_session.commit()

    runtime_user = runtime_session.get(User, user.id)
    assert runtime_user is not None
    runtime_session.delete(runtime_user)
    runtime_session.commit()

    assert runtime_session.get(User, user.id) is None
    remaining = runtime_session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    ).all()
    assert remaining == []
