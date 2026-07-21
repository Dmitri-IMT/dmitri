from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from api.models import persistence
from api.models.identity import Invite, Org, User
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]

IDENTITY_TABLES = ("orgs", "users", "invites")


def _load_identity_migration():
    path = next((ROOT / "alembic/versions").glob("*_identity_schema.py"))
    spec = importlib.util.spec_from_file_location("dmi58_identity", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _simulate_upgrade(module, monkeypatch: pytest.MonkeyPatch):
    metadata = sa.MetaData()
    created: dict[str, sa.Table] = {}
    added_columns: list[tuple[str, str, bool]] = []
    indexes: list[tuple[str, str, list[object], bool]] = []
    foreign_keys: list[tuple[str, str, str]] = []
    executed: list[str] = []

    def create_table(name: str, *elements: object) -> None:
        created[name] = sa.Table(name, metadata, *elements)

    def add_column(table: str, column: sa.Column) -> None:
        added_columns.append((table, column.name, column.nullable))

    def create_index(
        name: str, table: str, columns: list[object], *, unique: bool = False
    ) -> None:
        indexes.append((name, table, columns, unique))

    def create_foreign_key(
        name: str,
        source: str,
        referent: str,
        local_cols: list[str],
        remote_cols: list[str],
        **_: object,
    ) -> None:
        foreign_keys.append((source, referent, f"{local_cols}->{remote_cols}"))

    def execute(sql: object) -> None:
        executed.append(" ".join(str(sql).split()))

    monkeypatch.setattr(module.op, "create_table", create_table)
    monkeypatch.setattr(module.op, "add_column", add_column)
    monkeypatch.setattr(module.op, "create_index", create_index)
    monkeypatch.setattr(module.op, "create_foreign_key", create_foreign_key)
    monkeypatch.setattr(module.op, "execute", execute)

    module.upgrade()
    return created, added_columns, indexes, foreign_keys, executed


def test_migration_creates_identity_tables_and_scopes_scans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_identity_migration()
    created, added_columns, indexes, foreign_keys, _ = _simulate_upgrade(
        module, monkeypatch
    )

    assert tuple(created) == IDENTITY_TABLES

    # unique email per org is case-insensitive, single-use invite token is unique
    index_by_name = {name: (table, unique) for name, table, _, unique in indexes}
    assert index_by_name["ix_users_org_email"] == ("users", True)
    assert index_by_name["ix_invites_token_hash"] == ("invites", True)
    assert "ix_scans_org_id" in index_by_name

    # role enum enforced via CHECK on both identity tables
    for table_name in ("users", "invites"):
        checks = [
            constraint
            for constraint in created[table_name].constraints
            if isinstance(constraint, sa.CheckConstraint)
        ]
        assert any("role" in str(check.sqltext).lower() for check in checks)

    # org_id lands on scans from this first identity migration, nullable, FK to orgs
    assert ("scans", "org_id", True) in added_columns
    assert ("scans", "orgs", "['org_id']->['id']") in foreign_keys


def test_migration_extends_security_fence_without_sequences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_identity_migration()
    _, _, _, _, executed = _simulate_upgrade(module, monkeypatch)

    for table in IDENTITY_TABLES:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in executed

    qualified = ", ".join(f"public.{table}" for table in IDENTITY_TABLES)
    assert (
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {qualified} TO dmitri_runtime"
        in executed
    )
    # UUID primary keys => no sequences to grant, and the runtime never gets DELETE
    assert not any("SEQUENCE" in statement for statement in executed)
    assert not any(
        "DELETE" in statement and "dmitri_runtime" in statement
        for statement in executed
    )
    # baseline already owns the runtime role; this migration must not recreate it
    assert not any("CREATE ROLE" in statement for statement in executed)


def test_models_registered_and_scans_org_id_nullable() -> None:
    tables = persistence.SQLModel.metadata.tables
    assert {"orgs", "users", "invites"} <= set(tables)
    org_id = tables["scans"].columns["org_id"]
    assert org_id.nullable is True
    assert {fk.target_fullname for fk in org_id.foreign_keys} == {"orgs.id"}


def _seed_org(session: Session) -> Org:
    org = Org(name="Acme")
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def test_duplicate_email_per_org_is_rejected_case_insensitive(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
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


def test_invalid_role_is_rejected(administrative_session: Session) -> None:
    org = _seed_org(administrative_session)
    administrative_session.add(
        User(
            org_id=org.id,
            email="bob@corp.com",
            password_hash="x",
            role="superuser",
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_invite_token_is_single_use_unique(
    administrative_session: Session,
) -> None:
    org = _seed_org(administrative_session)
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    for email in ("carol@corp.com", "dave@corp.com"):
        administrative_session.add(
            Invite(
                org_id=org.id,
                email=email,
                role="viewer",
                token_hash="shared-hash",
                expires_at=expires,
            )
        )
    with pytest.raises(sa.exc.IntegrityError):
        administrative_session.commit()
    administrative_session.rollback()


def test_scan_accepts_org_scope(administrative_session: Session) -> None:
    org = _seed_org(administrative_session)
    scan = persistence.ScanRecord(
        scan_id=uuid4(),
        org_id=org.id,
        timestamp=datetime.now(timezone.utc),
        subnet="10.0.0.0/24",
        target_mode="subnet",
        scan_profile="lan",
    )
    administrative_session.add(scan)
    administrative_session.commit()
    administrative_session.refresh(scan)
    assert scan.org_id == org.id
