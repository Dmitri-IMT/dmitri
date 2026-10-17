from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import BIGINT

ROOT = Path(__file__).resolve().parents[1]


def _migration():
    path = ROOT / "alembic/versions/20261017_41_remote_agent_updates.py"
    spec = importlib.util.spec_from_file_location("agent_updates_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_uses_current_chain_head() -> None:
    migration = _migration()
    assert migration.revision == "20261017_41"
    assert migration.down_revision == "20260928_38"


def test_migration_preserves_existing_rows_and_nullable_versions(
    migrated_database,
) -> None:
    from conftest import _migrate

    _migrate(migrated_database, "20260928_38")
    org_id, agent_id, scan_id, command_id = (uuid4() for _ in range(4))
    now = datetime.now(timezone.utc)
    inserts = (
        (
            "INSERT INTO orgs (id, name, created_at) "
            "VALUES (:id, 'migration-preservation', :now)",
            {"id": org_id, "now": now},
        ),
        (
            "INSERT INTO agents (id, org_id, display_name, public_key, created_at) "
            "VALUES (:id, :org, 'preserved-agent', :key, :now)",
            {"id": agent_id, "org": org_id, "key": b"a" * 32, "now": now},
        ),
        (
            "INSERT INTO scans (scan_id, org_id, agent_id, timestamp, subnet, "
            "scan_mode, status, coverage_json, created_at) VALUES "
            "(:id, :org, :agent, :now, '10.0.0.0/24', 'full', 'completed', '[]', :now)",
            {"id": scan_id, "org": org_id, "agent": agent_id, "now": now},
        ),
        (
            "INSERT INTO commands (id, org_id, agent_id, scan_id, scan_mode, "
            "subnet, status, created_at) VALUES "
            "(:id, :org, :agent, :scan, 'full', '10.0.0.0/24', 'completed', :now)",
            {
                "id": command_id,
                "org": org_id,
                "agent": agent_id,
                "scan": scan_id,
                "now": now,
            },
        ),
    )
    with migrated_database.begin() as connection:
        for query, params in inserts:
            connection.execute(sa.text(query), params)

    _migrate(migrated_database, "head")
    with migrated_database.begin() as connection:
        inspector = sa.inspect(connection)
        from api.models.agent_update import AgentRelease, AgentReleaseCatalogState

        for table in (
            "agent_releases",
            "agent_updates",
            "agent_update_events",
            "agent_release_catalog_state",
        ):
            assert inspector.has_table(table)
        agent_columns = {
            column["name"]: column for column in inspector.get_columns("agents")
        }
        version_columns = (
            "observed_version",
            "observed_package_version",
            "version_observed_at",
            "version_observed_session_id",
        )
        assert all(agent_columns[name]["nullable"] for name in version_columns)
        release_columns = {
            column["name"]: column
            for column in inspector.get_columns("agent_releases")
        }
        catalog_columns = {
            column["name"]: column
            for column in inspector.get_columns("agent_release_catalog_state")
        }
        assert isinstance(
            AgentRelease.__table__.c.size_bytes.type,
            type(release_columns["size_bytes"]["type"]),
        )
        assert isinstance(
            AgentReleaseCatalogState.__table__.c.generation.type,
            type(catalog_columns["generation"]["type"]),
        )
        for table, column, row_id in (
            ("agents", "id", agent_id),
            ("scans", "scan_id", scan_id),
            ("commands", "id", command_id),
        ):
            query = sa.text(f"SELECT count(*) FROM {table} WHERE {column}=:id")
            assert connection.execute(query, {"id": row_id}).scalar_one() == 1

    _migrate(migrated_database, "20260928_38")
    with migrated_database.begin() as connection:
        for table, column, row_id in (
            ("agents", "id", agent_id),
            ("scans", "scan_id", scan_id),
            ("commands", "id", command_id),
        ):
            query = sa.text(f"SELECT count(*) FROM {table} WHERE {column}=:id")
            assert connection.execute(query, {"id": row_id}).scalar_one() == 1
    _migrate(migrated_database, "head")


def test_downgrade_refuses_persisted_update(migrated_database) -> None:
    from api.models.agent_update import AgentRelease, AgentUpdate
    from api.models.command import Agent
    from api.models.identity import Org, User
    from conftest import _migrate
    from sqlmodel import Session

    now = datetime.now(timezone.utc)
    with Session(migrated_database) as session:
        org = Org(name=f"downgrade-{uuid4()}")
        user = User(
            org_id=org.id,
            email=f"{uuid4()}@example.test",
            password_hash="x",
            role="admin",
        )
        agent = Agent(org_id=org.id, display_name="downgrade", public_key=b"b" * 32)
        release = AgentRelease(
            source_commit="a" * 40,
            upstream_version="1.0",
            package_version="1.0-1",
            architecture="arm64",
            suite="trixie",
            sha256="c" * 64,
            size_bytes=1,
            required_protocol_version=1,
            required_updater_version=1,
            published_at=now,
        )
        session.add(org)
        session.flush()
        session.add_all([user, agent, release])
        session.flush()
        session.add(
            AgentUpdate(
                org_id=org.id,
                agent_id=agent.id,
                actor_id=user.id,
                actor_display_snapshot="admin",
                idempotency_key="persisted",
                request_digest="d" * 64,
                release_id=release.id,
                target_version="1.0",
                target_package_version="1.0-1",
            )
        )
        session.commit()

    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        _migrate(migrated_database, "20260928_38")


def test_large_integer_columns_match_migration() -> None:
    from api.models.agent_update import AgentRelease, AgentReleaseCatalogState

    assert isinstance(AgentRelease.__table__.c.size_bytes.type, BIGINT)
    assert isinstance(AgentReleaseCatalogState.__table__.c.generation.type, BIGINT)
