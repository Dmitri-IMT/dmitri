from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20261002_39_scan_live_progress.py"
    spec = importlib.util.spec_from_file_location("scan_live_progress", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = _load_migration()

    assert migration.revision == "20261002_39"
    assert migration.down_revision == "20260928_38"


def test_migration_adds_nullable_snapshot_and_monotonic_sequence(monkeypatch) -> None:
    migration = _load_migration()
    added: list[tuple[str, object]] = []
    dropped: list[tuple[str, str]] = []
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

    assert [column.name for _, column in added] == [
        "progress_json",
        "progress_seq",
        "progress_updated_at",
    ]
    assert added[0][1].nullable is True
    assert added[1][1].nullable is False
    assert str(added[1][1].server_default.arg) == "0"
    assert added[2][1].nullable is True

    migration.downgrade()

    assert dropped == [
        ("scans", "progress_updated_at"),
        ("scans", "progress_seq"),
        ("scans", "progress_json"),
    ]
