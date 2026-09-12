from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20260903_18_nspi_options.py"
    spec = importlib.util.spec_from_file_location("nspi_options_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_chain_and_operations(monkeypatch) -> None:
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

    assert migration.revision == "20260903_18"
    assert migration.down_revision == "20260811_17"
    assert added[0][0] == "commands"
    assert added[0][1].name == "nspi_options"
    assert isinstance(added[0][1].type, sa.JSON)
    assert dropped == [("commands", "nspi_options")]
