from __future__ import annotations

from api.models.persistence import SQLModel
from sqlalchemy import UniqueConstraint


def _unique_column_sets(table_name: str) -> set[frozenset[str]]:
    table = SQLModel.metadata.tables[table_name]
    return {
        frozenset(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_targets(table_name: str, column_name: str) -> set[str]:
    column = SQLModel.metadata.tables[table_name].columns[column_name]
    return {fk.target_fullname for fk in column.foreign_keys}


def test_host_ports_columns_and_unique_key():
    table = SQLModel.metadata.tables["host_ports"]
    assert set(table.columns.keys()) == {
        "id",
        "host_id",
        "port",
        "protocol",
        "service",
        "version",
        "first_seen_at",
        "last_seen_at",
    }
    assert frozenset({"host_id", "port", "protocol"}) in _unique_column_sets(
        "host_ports"
    )
    assert _foreign_key_targets("host_ports", "host_id") == {"hosts.id"}


def test_host_ports_does_not_store_openness():
    table = SQLModel.metadata.tables["host_ports"]
    assert "state" not in table.columns
    assert "closed_at" not in table.columns


def test_host_findings_columns_and_unique_key():
    table = SQLModel.metadata.tables["host_findings"]
    assert set(table.columns.keys()) == {
        "id",
        "host_id",
        "dedupe_key",
        "first_seen_at",
        "last_seen_at",
        "fixed_at",
    }
    assert frozenset({"host_id", "dedupe_key"}) in _unique_column_sets("host_findings")
    assert _foreign_key_targets("host_findings", "host_id") == {"hosts.id"}
    assert table.c.fixed_at.nullable is True


def test_host_findings_reaches_the_org_through_hosts():
    assert "org_id" not in SQLModel.metadata.tables["host_findings"].columns


def test_hosts_machine_type_is_nullable_and_vulnerability_count_defaults_to_zero():
    table = SQLModel.metadata.tables["hosts"]
    assert table.c.machine_type.nullable is True
    assert table.c.vulnerability_count.nullable is False
    assert table.c.vulnerability_count.server_default.arg == "0"


def test_hosts_keeps_the_machine_page_fields():
    table = SQLModel.metadata.tables["hosts"]
    assert {"vendor", "open_ports_count", "highest_severity"} <= set(
        table.columns.keys()
    )


def test_per_scan_evidence_tables_are_unchanged():
    findings = SQLModel.metadata.tables["findings"]
    for absent in ("host_hostname", "first_seen_at", "last_seen_at", "fixed_at"):
        assert absent not in findings.columns
    assert set(SQLModel.metadata.tables["ports"].columns.keys()) == {
        "id",
        "scan_host_id",
        "port",
        "protocol",
        "state",
        "created_at",
    }
