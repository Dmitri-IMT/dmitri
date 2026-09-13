from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260912_24"
down_revision = "20260912_23"
branch_labels = None
depends_on = None

TABLE = "ai_scan_analyses"
STATUSES = ("pending", "processing", "completed", "failed")


def _revoke_supabase_roles() -> None:
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE public.{TABLE}_id_seq FROM {role};
                END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column(
            "context_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "prompt_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "context_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{status}'" for status in STATUSES) + ")",
            name="ck_ai_scan_analyses_status",
        ),
        sa.CheckConstraint(
            "status != 'completed' OR analysis_json IS NOT NULL",
            name="ck_ai_scan_analyses_completed_payload",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_ai_scan_analyses_attempts"),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scans.scan_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id"),
        sa.UniqueConstraint("scan_id"),
    )
    op.create_index(
        "ix_ai_scan_analyses_analysis_id",
        TABLE,
        ["analysis_id"],
        unique=True,
    )
    op.create_index(
        "ix_ai_scan_analyses_scan_id",
        TABLE,
        ["scan_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_scan_analyses_status",
        TABLE,
        ["status"],
        unique=False,
    )

    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")
    _revoke_supabase_roles()
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{TABLE} TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE public.{TABLE}_id_seq TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM dmitri_runtime"
    )
    op.drop_index("ix_ai_scan_analyses_status", table_name=TABLE)
    op.drop_index("ix_ai_scan_analyses_scan_id", table_name=TABLE)
    op.drop_index("ix_ai_scan_analyses_analysis_id", table_name=TABLE)
    op.drop_table(TABLE)
