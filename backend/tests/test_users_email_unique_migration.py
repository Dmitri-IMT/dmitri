from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from api.models.identity import Org, User
from conftest import _migrate
from sqlalchemy.engine import Engine
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260724_10_users_email_global_unique.py"
    spec = importlib.util.spec_from_file_location(
        "task_3_users_email_global_unique", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()
    assert migration.revision == "20260724_10"
    assert migration.down_revision == "20260724_09"


def test_migration_upgrade_replaces_index(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[str] = []
    created: list[tuple[str, str, list[object], bool]] = []

    monkeypatch.setattr(
        migration.op, "drop_index", lambda name, table_name=None: dropped.append(name)
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, *, unique=False: created.append(
            (name, table, columns, unique)
        ),
    )

    migration.upgrade()

    assert dropped == ["ix_users_org_email"]
    assert len(created) == 1
    name, table, columns, unique = created[0]
    assert name == "ix_users_email"
    assert table == "users"
    assert unique is True
    assert len(columns) == 1
    assert str(columns[0]) == "lower(email)"


def test_migration_downgrade_restores_org_scoped_index(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[str] = []
    created: list[tuple[str, str, list[object], bool]] = []

    monkeypatch.setattr(
        migration.op, "drop_index", lambda name, table_name=None: dropped.append(name)
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, *, unique=False: created.append(
            (name, table, columns, unique)
        ),
    )

    migration.downgrade()

    assert dropped == ["ix_users_email"]
    assert len(created) == 1
    name, table, columns, unique = created[0]
    assert name == "ix_users_org_email"
    assert table == "users"
    assert unique is True
    assert [str(column) for column in columns] == ["org_id", "lower(email)"]


def _index_defs(engine: Engine) -> dict[str, str]:
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'users'"
            )
        ).all()
    return {name: indexdef for name, indexdef in rows}


def test_live_migration_round_trip(postgres_engine: Engine) -> None:
    _migrate(postgres_engine, "20260724_09")
    defs_before = _index_defs(postgres_engine)
    assert "ix_users_org_email" in defs_before
    assert "ix_users_email" not in defs_before

    _migrate(postgres_engine, "head")
    defs_after = _index_defs(postgres_engine)
    assert "ix_users_org_email" not in defs_after
    assert "ix_users_email" in defs_after
    assert "UNIQUE INDEX" in defs_after["ix_users_email"]
    assert "lower((email)::text)" in defs_after["ix_users_email"]
    assert "org_id" not in defs_after["ix_users_email"]

    _migrate(postgres_engine, "20260724_09")
    defs_down = _index_defs(postgres_engine)
    assert "ix_users_email" not in defs_down
    assert "ix_users_org_email" in defs_down
    assert "UNIQUE INDEX" in defs_down["ix_users_org_email"]
    assert "org_id" in defs_down["ix_users_org_email"]
    assert "lower((email)::text)" in defs_down["ix_users_org_email"]

    _migrate(postgres_engine, "head")


def test_live_upgrade_adds_no_org_id_index(migrated_database: Engine) -> None:
    defs = _index_defs(migrated_database)
    assert "ix_users_org_email" not in defs
    assert all("org_id" not in indexdef for indexdef in defs.values())


def test_live_ck_users_role_unchanged(migrated_database: Engine) -> None:
    with migrated_database.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'public.users'::regclass AND contype = 'c'"
            )
        ).all()
    constraints = {name: condef for name, condef in rows}
    condef = constraints["ck_users_role"].lower()
    assert "role" in condef
    assert "admin" in condef
    assert "viewer" in condef


def test_live_cross_org_duplicate_email_is_rejected(
    administrative_session: Session,
) -> None:
    org_one = Org(name="Acme")
    org_two = Org(name="Globex")
    administrative_session.add(org_one)
    administrative_session.add(org_two)
    administrative_session.commit()
    administrative_session.refresh(org_one)
    administrative_session.refresh(org_two)

    administrative_session.add(
        User(
            org_id=org_one.id,
            email="shared@corp.com",
            password_hash="x",
            role="admin",
        )
    )
    administrative_session.commit()

    administrative_session.add(
        User(
            org_id=org_two.id,
            email="shared@corp.com",
            password_hash="y",
            role="viewer",
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_live_case_insensitive_duplicate_email_is_rejected(
    administrative_session: Session,
) -> None:
    org = Org(name="Acme")
    administrative_session.add(org)
    administrative_session.commit()
    administrative_session.refresh(org)

    administrative_session.add(
        User(
            org_id=org.id,
            email="alice@corp.com",
            password_hash="x",
            role="admin",
        )
    )
    administrative_session.commit()

    administrative_session.add(
        User(
            org_id=org.id,
            email="ALICE@corp.com",
            password_hash="y",
            role="viewer",
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()
