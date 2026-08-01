from __future__ import annotations

import sqlalchemy as sa
from api.models import command  # noqa: F401
from api.models.persistence import SQLModel


def test_agent_table_registers_on_metadata():
    assert "agents" in SQLModel.metadata.tables


def test_command_table_registers_on_metadata():
    assert "commands" in SQLModel.metadata.tables


def test_agent_columns_match_expected_set():
    table = SQLModel.metadata.tables["agents"]
    assert set(table.columns.keys()) == {
        "id",
        "org_id",
        "display_name",
        "public_key",
        "revoked_at",
        "last_seen_at",
        "connected_at",
        "created_at",
    }


def test_agent_has_no_plaintext_or_hash_secret_columns():
    table = SQLModel.metadata.tables["agents"]
    assert "secret" not in table.columns
    assert "secret_hash" not in table.columns
    assert "online" not in table.columns


def test_command_columns_match_expected_set():
    table = SQLModel.metadata.tables["commands"]
    assert set(table.columns.keys()) == {
        "id",
        "org_id",
        "agent_id",
        "scan_id",
        "scan_mode",
        "subnet",
        "status",
        "error_code",
        "created_at",
        "delivered_at",
        "started_at",
        "completed_at",
    }


def test_command_has_exactly_four_timestamp_columns_no_uploading_at():
    table = SQLModel.metadata.tables["commands"]
    timestamp_columns = {
        "created_at",
        "delivered_at",
        "started_at",
        "completed_at",
    }
    assert timestamp_columns <= set(table.columns.keys())
    assert "uploading_at" not in table.columns


def test_command_scan_id_is_nullable_and_unique():
    column = SQLModel.metadata.tables["commands"].columns["scan_id"]
    assert column.nullable is True
    assert column.unique is True


def test_agent_nonce_timestamp_columns_are_timezone_aware():
    table = SQLModel.metadata.tables["agent_nonces"]
    assert isinstance(table.c.expires_at.type, sa.DateTime)
    assert table.c.expires_at.type.timezone is True
    assert isinstance(table.c.created_at.type, sa.DateTime)
    assert table.c.created_at.type.timezone is True
