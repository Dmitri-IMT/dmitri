from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from conftest import _migrate

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260908_19_operating_system_inventory.py"
    spec = importlib.util.spec_from_file_location(
        "operating_system_inventory_migration", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_nullable_json_operations(monkeypatch) -> None:
    migration = _load_migration()
    added = []
    dropped = []
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append((table, column)),
    )

    migration.upgrade()
    migration.downgrade()

    assert migration.revision == "20260908_19"
    assert migration.down_revision == "20260903_18"
    assert [table for table, _column in added] == ["scan_hosts", "hosts"]
    for _table, column in added:
        assert column.name == "operating_system_json"
        assert isinstance(column.type, sa.JSON)
        assert column.nullable is True
    assert dropped == [
        ("hosts", "operating_system_json"),
        ("scan_hosts", "operating_system_json"),
    ]


def test_real_upgrade_and_downgrade_add_and_remove_both_columns(
    migrated_database,
) -> None:
    engine = migrated_database
    try:
        _migrate(engine, "20260903_18")
        before = sa.inspect(engine)
        assert "operating_system_json" not in {
            column["name"] for column in before.get_columns("scan_hosts")
        }
        assert "operating_system_json" not in {
            column["name"] for column in before.get_columns("hosts")
        }

        _migrate(engine, "20260908_19")
        upgraded = sa.inspect(engine)
        for table in ("scan_hosts", "hosts"):
            column = next(
                column
                for column in upgraded.get_columns(table)
                if column["name"] == "operating_system_json"
            )
            assert isinstance(column["type"], sa.JSON)
            assert column["nullable"] is True

        _migrate(engine, "20260903_18")
        downgraded = sa.inspect(engine)
        for table in ("scan_hosts", "hosts"):
            assert "operating_system_json" not in {
                column["name"] for column in downgraded.get_columns(table)
            }
    finally:
        _migrate(engine, "head")
