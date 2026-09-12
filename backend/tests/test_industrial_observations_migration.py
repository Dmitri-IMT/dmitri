from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from conftest import _alembic_config

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260912_21_industrial_observations.py"
    spec = importlib.util.spec_from_file_location(
        "industrial_observations_migration", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_is_empty_merge_from_prior_heads(monkeypatch) -> None:
    migration = _load_migration()
    created: list[str] = []
    dropped: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *args, **kwargs: created.append(name),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda name: dropped.append(name),
    )
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "drop_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "drop_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op, "create_foreign_key", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        migration.op, "drop_constraint", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(migration.op, "execute", lambda *args, **kwargs: None)

    migration.upgrade()
    migration.downgrade()

    assert migration.revision == "20260912_21"
    assert migration.down_revision == "20260912_20"
    assert created == ["industrial_services", "modbus_units"]
    assert dropped == ["modbus_units", "industrial_services"]


def test_real_upgrade_from_released_state_and_reversible(migrated_database) -> None:
    engine = migrated_database
    config = _alembic_config()
    try:
        command.downgrade(config, "20260912_20")
        before = sa.inspect(engine)
        assert "industrial_services" not in before.get_table_names()
        assert "modbus_units" not in before.get_table_names()
        assert "ot_digest_key" not in {
            column["name"] for column in before.get_columns("orgs")
        }
        assert "modbus_unit_id" not in {
            column["name"] for column in before.get_columns("findings")
        }

        command.upgrade(config, "20260912_21")
        upgraded = sa.inspect(engine)
        assert "industrial_services" in upgraded.get_table_names()
        assert "modbus_units" in upgraded.get_table_names()
        assert "ot_digest_key" in {
            column["name"] for column in upgraded.get_columns("orgs")
        }
        modbus_fk = [
            fk
            for fk in upgraded.get_foreign_keys("findings")
            if "modbus_unit_id" in fk.get("constrained_columns", [])
        ]
        assert modbus_fk

        command.downgrade(config, "20260912_20")
        downgraded = sa.inspect(engine)
        assert "industrial_services" not in downgraded.get_table_names()
        assert "modbus_units" not in downgraded.get_table_names()

        command.downgrade(config, "20260905_19")
        command.upgrade(config, "head")
        at_head = sa.inspect(engine)
        assert "industrial_services" in at_head.get_table_names()
        assert "modbus_units" in at_head.get_table_names()
    finally:
        command.upgrade(config, "head")
