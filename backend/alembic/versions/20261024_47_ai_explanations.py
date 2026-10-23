from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision = "20261024_47"
down_revision = "20261023_46"
branch_labels = None
depends_on = None

TABLE = "ai_explanations"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", AutoString(), nullable=False),
        sa.Column("context_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("language", AutoString(), nullable=False),
        sa.Column("prompt_version", AutoString(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope IN ('scan', 'host')", name="ck_ai_explanations_scope"
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.scan_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "scope",
            "context_id",
            "language",
            "prompt_version",
            name="uq_ai_explanations_context",
        ),
    )
    op.create_index("ix_ai_explanations_context_id", TABLE, ["context_id"])
    op.create_index("ix_ai_explanations_scan_id", TABLE, ["scan_id"])
    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")
    for role in ("anon", "authenticated"):
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE public.{TABLE}_id_seq
                    FROM {role};
                END IF;
            END $$
        """)
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM PUBLIC")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{TABLE} "
        "TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE public.{TABLE}_id_seq TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM dmitri_runtime")
    op.drop_index("ix_ai_explanations_scan_id", table_name=TABLE)
    op.drop_index("ix_ai_explanations_context_id", table_name=TABLE)
    op.drop_table(TABLE)
