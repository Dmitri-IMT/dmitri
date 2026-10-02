from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from api.models import command  # noqa: F401
from api.models.persistence import SQLModel
from api.schemas.agent_frames import AgentStatusFrame
from api.schemas.commands import CommandSummary
from api.schemas.read import ScanSummary


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
        "target_subnet",
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
        "nspi_options",
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


def test_cancelled_status_is_accepted_by_public_and_agent_schemas():
    command_summary = CommandSummary.model_validate(
        {
            "command_id": UUID("11111111-1111-4111-8111-111111111111"),
            "agent_id": UUID("22222222-2222-4222-8222-222222222222"),
            "status": "cancelled",
        }
    )
    scan_summary = ScanSummary.model_validate(
        {
            "scan_id": UUID("33333333-3333-4333-8333-333333333333"),
            "timestamp": "2026-09-27T12:00:00Z",
            "subnet": "10.0.0.0/24",
            "scan_mode": "standard",
            "status": "cancelled",
            "evidence_completeness": "unknown",
            "host_count": 0,
            "finding_count": 0,
        }
    )
    status_frame = AgentStatusFrame.model_validate(
        {
            "type": "status",
            "command_id": "44444444-4444-4444-8444-444444444444",
            "status": "cancelled",
        }
    )

    assert command_summary.status == "cancelled"
    assert scan_summary.status == "cancelled"
    assert status_frame.status == "cancelled"
