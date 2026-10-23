from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261022_45"
down_revision = "20261022_44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_clients",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(), sa.ForeignKey("mcp_clients.id"), nullable=False),
        sa.Column("resource", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_mcp_connections_user_id", "mcp_connections", ["user_id"])
    op.create_table(
        "mcp_authorizations",
        sa.Column("request_hash", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("mcp_clients.id"), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("mcp_connections.id", ondelete="CASCADE")),
        sa.Column("code_hash", sa.String()),
        sa.Column("exchanged_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_mcp_authorizations_code_hash", "mcp_authorizations", ["code_hash"], unique=True)
    op.create_table(
        "mcp_credentials",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("mcp_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('access', 'refresh')", name="ck_mcp_credentials_kind"),
    )
    op.create_index("ix_mcp_credentials_connection_id", "mcp_credentials", ["connection_id"])
    for table in ("mcp_clients", "mcp_connections", "mcp_authorizations", "mcp_credentials"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO dmitri_runtime")
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                f"THEN REVOKE ALL ON TABLE public.{table} FROM {role}; END IF; END $$"
            )


def downgrade() -> None:
    for table in ("mcp_credentials", "mcp_authorizations", "mcp_connections", "mcp_clients"):
        op.drop_table(table)
