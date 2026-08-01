from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260731_13"
down_revision = "20260727_12"
branch_labels = None
depends_on = None

_CHECK = "ck_commands_scan_id_or_expired"
_CHECK_EXPR = "scan_id IS NOT NULL OR status IN ('queued', 'expired')"
_ACTIVE_INDEX = "uq_commands_active_agent"
_ACTIVE_WHERE = "status IN ('queued', 'delivered', 'running', 'uploading')"

# 20260724_08 converted every naive timestamp column in the schema to
# timestamptz but its map omitted `agents` and `commands`. That was harmless
# while these columns were write-only; the stale sweep introduced here compares
# `agents.last_seen_at` against a timezone-aware cutoff, and Postgres resolves
# `timestamp < timestamptz` through the session TimeZone GUC — which nothing
# pins to UTC. Finish the 08 conversion for these two tables, same mechanism.
NAIVE_TIMESTAMP_COLUMNS = {
    "agents": ("revoked_at", "last_seen_at", "created_at"),
    "commands": ("created_at", "delivered_at", "started_at", "completed_at"),
}


def _retype(target: str) -> None:
    for table, columns in NAIVE_TIMESTAMP_COLUMNS.items():
        for column in columns:
            op.execute(
                f"ALTER TABLE public.{table} ALTER COLUMN {column} "
                f"TYPE {target} USING {column} AT TIME ZONE 'UTC'"
            )


def upgrade() -> None:
    bind = op.get_bind()
    bad = bind.execute(
        sa.text(
            "SELECT id FROM commands WHERE scan_id IS NULL "
            "AND status NOT IN ('queued', 'expired')"
        )
    ).fetchall()
    if bad:
        ids = ", ".join(str(row[0]) for row in bad)
        raise RuntimeError(
            f"commands with null scan_id and non-expired status: {ids}"
        )

    op.alter_column(
        "commands",
        "scan_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_check_constraint(_CHECK, "commands", _CHECK_EXPR)
    op.create_index(
        _ACTIVE_INDEX,
        "commands",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_WHERE),
    )
    _retype("timestamptz")
    op.add_column(
        "agents",
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    bad = bind.execute(
        sa.text("SELECT id FROM commands WHERE scan_id IS NULL")
    ).fetchall()
    if bad:
        ids = ", ".join(str(row[0]) for row in bad)
        raise RuntimeError(f"commands with null scan_id block downgrade: {ids}")

    op.drop_column("agents", "connected_at")
    _retype("timestamp")
    op.drop_index(_ACTIVE_INDEX, table_name="commands")
    op.drop_constraint(_CHECK, "commands", type_="check")
    op.alter_column(
        "commands",
        "scan_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
