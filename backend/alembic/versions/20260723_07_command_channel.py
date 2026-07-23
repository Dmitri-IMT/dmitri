from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260723_07"
down_revision = "20260722_06"
branch_labels = None
depends_on = None

COMMAND_TABLES = ("agents", "commands")


def _qualified(objects: tuple[str, ...]) -> str:
    return ", ".join(f"public.{name}" for name in objects)


def _revoke_supabase_roles() -> None:
    tables = _qualified(COMMAND_TABLES)
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {tables} FROM {role};
                END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("secret_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("secret_key_version", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_org_id", "agents", ["org_id"], unique=False)

    op.create_table(
        "commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("scan_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subnet", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("error_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", name="uq_commands_scan_id"),
    )
    op.create_index("ix_commands_org_id", "commands", ["org_id"], unique=False)
    op.create_index("ix_commands_agent_id", "commands", ["agent_id"], unique=False)

    for table in COMMAND_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    _revoke_supabase_roles()

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {_qualified(COMMAND_TABLES)} "
        "TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE ALL PRIVILEGES ON TABLE {_qualified(COMMAND_TABLES)} "
        "FROM dmitri_runtime"
    )
    op.drop_index("ix_commands_agent_id", table_name="commands")
    op.drop_index("ix_commands_org_id", table_name="commands")
    op.drop_table("commands")
    op.drop_index("ix_agents_org_id", table_name="agents")
    op.drop_table("agents")
