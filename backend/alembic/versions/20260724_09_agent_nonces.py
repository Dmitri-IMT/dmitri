from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260724_09"
down_revision = "20260724_08"
branch_labels = None
depends_on = None

TABLE = "agent_nonces"


def _revoke_supabase_roles() -> None:
    table = f"public.{TABLE}"
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {table} FROM {role};
                END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("nonce", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "nonce", name="uq_agent_nonces_agent_id_nonce"),
    )
    op.create_index(
        "ix_agent_nonces_expires_at", TABLE, ["expires_at"], unique=False
    )

    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")

    _revoke_supabase_roles()

    op.execute(
        f"GRANT SELECT, INSERT, DELETE ON TABLE public.{TABLE} TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM dmitri_runtime")
    op.drop_index("ix_agent_nonces_expires_at", table_name=TABLE)
    op.drop_table(TABLE)
