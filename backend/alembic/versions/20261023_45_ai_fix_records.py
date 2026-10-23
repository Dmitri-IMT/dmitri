from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision = "20261023_45"
down_revision = "20261023_44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_fix_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", AutoString(), nullable=False),
        sa.Column("cve_id", AutoString(), nullable=False),
        sa.Column("product", AutoString(), nullable=False),
        sa.Column("version", AutoString(), nullable=False),
        sa.Column("research_version", AutoString(), nullable=False),
        sa.Column("record_json", sa.JSON(), nullable=False),
        sa.Column("has_fix", sa.Boolean(), nullable=False),
        sa.Column("kev_fingerprint", AutoString(), nullable=False),
        sa.Column("nvd_last_modified", AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_fix_records_cache_key", "ai_fix_records", ["cache_key"], unique=True
    )
    op.create_index("ix_ai_fix_records_cve_id", "ai_fix_records", ["cve_id"])
    op.create_index("ix_ai_fix_records_expires_at", "ai_fix_records", ["expires_at"])
    op.execute("ALTER TABLE public.ai_fix_records ENABLE ROW LEVEL SECURITY")
    for role in ("anon", "authenticated"):
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.ai_fix_records
                    FROM {role};
                END IF;
            END $$
        """)
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.ai_fix_records FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.ai_fix_records "
        "TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.ai_fix_records FROM dmitri_runtime"
    )
    op.drop_index("ix_ai_fix_records_expires_at", table_name="ai_fix_records")
    op.drop_index("ix_ai_fix_records_cve_id", table_name="ai_fix_records")
    op.drop_index("ix_ai_fix_records_cache_key", table_name="ai_fix_records")
    op.drop_table("ai_fix_records")
