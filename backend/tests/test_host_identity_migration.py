from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from api.models import persistence

ROOT = Path(__file__).resolve().parents[1]

OP_METHODS = (
    "create_table",
    "drop_table",
    "add_column",
    "drop_column",
    "alter_column",
    "rename_table",
    "create_index",
    "drop_index",
    "create_foreign_key",
    "drop_constraint",
    "execute",
)


def _load_migration(glob: str):
    path = next((ROOT / "alembic/versions").glob(glob))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(monkeypatch: pytest.MonkeyPatch, module) -> list[tuple[str, tuple, dict]]:
    calls: list[tuple[str, tuple, dict]] = []
    for name in OP_METHODS:

        def make(name):
            def fn(*args, **kwargs):
                calls.append((name, args, kwargs))

            return fn

        monkeypatch.setattr(module.op, name, make(name))
    return calls


def _find(calls, name):
    return [(args, kwargs) for method, args, kwargs in calls if method == name]


def test_migration_03_swaps_scan_mode_status_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration("*_scan_mode_status.py")
    calls = _record(monkeypatch, module)

    module.upgrade()

    dropped = {args[1] for args, _ in _find(calls, "drop_column")}
    assert dropped == {"target_mode", "scan_profile"}
    added = {args[1].name: args[1] for args, _ in _find(calls, "add_column")}
    assert set(added) == {"scan_mode", "status"}
    assert added["scan_mode"].nullable is False
    assert added["status"].nullable is False
    assert added["status"].server_default is not None

    calls.clear()
    module.downgrade()
    dropped_down = {args[1] for args, _ in _find(calls, "drop_column")}
    assert dropped_down == {"scan_mode", "status"}
    added_down = {args[1].name for args, _ in _find(calls, "add_column")}
    assert added_down == {"target_mode", "scan_profile"}


def test_migration_04_renames_devices_to_scan_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration("*_scan_host_rename.py")
    calls = _record(monkeypatch, module)

    module.upgrade()

    renames = _find(calls, "rename_table")
    assert renames == [(("devices", "scan_hosts"), {})]
    alters = {args[0]: args[1] for args, _ in _find(calls, "alter_column")}
    assert alters["ports"] == "device_id"
    assert alters["findings"] == "device_id"
    for args, kwargs in _find(calls, "alter_column"):
        assert kwargs.get("new_column_name") == "scan_host_id"
    executed = [" ".join(str(args[0]).split()) for args, _ in _find(calls, "execute")]
    assert any(
        "ALTER SEQUENCE devices_id_seq RENAME TO scan_hosts_id_seq" in statement
        for statement in executed
    )

    calls.clear()
    module.downgrade()
    renames_down = _find(calls, "rename_table")
    assert renames_down == [(("scan_hosts", "devices"), {})]
    for args, kwargs in _find(calls, "alter_column"):
        assert kwargs.get("new_column_name") == "device_id"


def test_migration_05_creates_hosts_table_with_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration("*_host_identity.py")
    calls = _record(monkeypatch, module)

    module.upgrade()

    created = [args[0] for args, _ in _find(calls, "create_table")]
    assert created == ["hosts"]

    added_columns = {args[1].name: args[1] for args, _ in _find(calls, "add_column")}
    assert added_columns["host_id"].nullable is True

    fks = _find(calls, "create_foreign_key")
    assert any(
        args[1] == "scan_hosts" and args[2] == "hosts" and args[3] == ["host_id"]
        for args, _ in fks
    )

    indexes = {
        args[0]: (args[1], kwargs) for args, kwargs in _find(calls, "create_index")
    }
    assert "ix_scan_hosts_host_id" in indexes
    assert indexes["ix_scan_hosts_host_id"][0] == "scan_hosts"
    assert "uq_hosts_org_identity" in indexes
    unique_index_kwargs = indexes["uq_hosts_org_identity"][1]
    assert unique_index_kwargs["unique"] is True
    assert unique_index_kwargs["postgresql_nulls_not_distinct"] is True

    executed = [" ".join(str(args[0]).split()) for args, _ in _find(calls, "execute")]
    assert "ALTER TABLE public.hosts ENABLE ROW LEVEL SECURITY" in executed
    assert "GRANT SELECT, INSERT, UPDATE ON hosts TO dmitri_runtime" in executed
    assert not any("SEQUENCE" in statement for statement in executed)
    assert not any("DELETE" in statement for statement in executed)
    assert not any("CREATE ROLE" in statement for statement in executed)

    calls.clear()
    module.downgrade()
    assert _find(calls, "drop_table") == [(("hosts",), {})]
    dropped_columns = {args[1] for args, _ in _find(calls, "drop_column")}
    assert "host_id" in dropped_columns


def test_migration_06_adds_finding_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration("*_finding_uuid.py")
    calls = _record(monkeypatch, module)

    module.upgrade()

    added_columns = {args[1].name: args[1] for args, _ in _find(calls, "add_column")}
    assert added_columns["finding_id"].nullable is True

    executed = [" ".join(str(args[0]).split()) for args, _ in _find(calls, "execute")]
    assert any("gen_random_uuid()" in statement for statement in executed)

    alters = _find(calls, "alter_column")
    assert any(
        args[0] == "findings"
        and args[1] == "finding_id"
        and kwargs.get("nullable") is False
        for args, kwargs in alters
    )

    indexes = {
        args[0]: (args[1], kwargs) for args, kwargs in _find(calls, "create_index")
    }
    assert "uq_findings_finding_id" in indexes
    assert indexes["uq_findings_finding_id"][0] == "findings"
    assert indexes["uq_findings_finding_id"][1]["unique"] is True

    calls.clear()
    module.downgrade()
    dropped_indexes = {args[0] for args, _ in _find(calls, "drop_index")}
    assert dropped_indexes == {"uq_findings_finding_id"}
    dropped_columns = {args[1] for args, _ in _find(calls, "drop_column")}
    assert "finding_id" in dropped_columns


def test_models_registered_with_renamed_and_new_tables() -> None:
    tables = persistence.SQLModel.metadata.tables
    assert {"scan_hosts", "hosts"} <= set(tables)
    assert "devices" not in tables

    scan_record_columns = tables["scans"].columns
    assert {"scan_mode", "status"} <= set(scan_record_columns.keys())
    assert "target_mode" not in scan_record_columns
    assert "scan_profile" not in scan_record_columns

    ports_columns = tables["ports"].columns
    assert "scan_host_id" in ports_columns
    findings_columns = tables["findings"].columns
    assert "scan_host_id" in findings_columns

    host_id = tables["scan_hosts"].columns["host_id"]
    assert {fk.target_fullname for fk in host_id.foreign_keys} == {"hosts.id"}

    unique_constraints = [
        constraint
        for constraint in tables["hosts"].constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert any(
        {column.name for column in constraint.columns} == {"org_id", "identity_key"}
        for constraint in unique_constraints
    )
