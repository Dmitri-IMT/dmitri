from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260804_14"
down_revision = "20260731_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
    )
    op.drop_table("artifacts")


def downgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("host_ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_scan_id", "artifacts", ["scan_id"], unique=False)

    op.execute("ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.artifacts FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.artifacts FROM authenticated;
            END IF;
        END
        $$
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON artifacts TO dmitri_runtime")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE artifacts_id_seq TO dmitri_runtime")

    op.drop_column("scans", "agent_id")
