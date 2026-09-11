from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260911_20_industrial_services_inventory.py"
    spec = importlib.util.spec_from_file_location(
        "industrial_services_inventory_migration", path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_merges_heads_and_adds_non_nullable_json(monkeypatch) -> None:
    migration = _load_migration()
    added = []
    altered = []
    dropped = []
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column)),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table, column, **kwargs: altered.append((table, column, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append((table, column)),
    )

    migration.upgrade()
    migration.downgrade()

    assert migration.revision == "20260911_20"
    assert migration.down_revision == ("20260905_19", "20260908_19")
    assert [table for table, _column in added] == ["scan_hosts", "hosts"]
    for _table, column in added:
        assert column.name == "industrial_services_json"
        assert isinstance(column.type, sa.JSON)
        assert column.nullable is False
        assert str(column.server_default.arg) == "'[]'::json"
    assert altered == [
        ("scan_hosts", "industrial_services_json", {"server_default": None}),
        ("hosts", "industrial_services_json", {"server_default": None}),
    ]
    assert dropped == [
        ("hosts", "industrial_services_json"),
        ("scan_hosts", "industrial_services_json"),
    ]
