from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260907_20"
down_revision = "20260905_19"
branch_labels = None
depends_on = None

NEW_TABLES = ("host_ports", "host_findings")

_MACHINE_TYPE_CONSTRAINT = "ck_hosts_machine_type"
# Spelled out rather than imported from api.core.machine_type: a revision is a
# frozen historical snapshot, so its SQL must not shift when the live vocabulary
# is edited. test_machine_inventory_migration.py asserts the two still agree.
_ALLOWED = (
    "'router', 'computer', 'camera', 'storage', 'tv', "
    "'phone', 'printer', 'sensor', 'unknown'"
)
_MACHINE_TYPE_CHECK = f"machine_type IS NULL OR machine_type IN ({_ALLOWED})"


def _revoke_supabase_roles(table_name: str) -> None:
    table = f"public.{table_name}"
    sequence = f"public.{table_name}_id_seq"
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {table} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE {sequence} FROM {role};
                END IF;
            END
            $$
            """
        )


def _secure(table_name: str) -> None:
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    _revoke_supabase_roles(table_name)
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table_name} "
        f"TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE public.{table_name}_id_seq TO dmitri_runtime"
    )


def upgrade() -> None:
    op.add_column(
        "hosts",
        sa.Column("machine_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "hosts",
        sa.Column(
            "vulnerability_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        _MACHINE_TYPE_CONSTRAINT, "hosts", _MACHINE_TYPE_CHECK
    )
    op.create_index(
        "ix_hosts_org_id_last_seen_at", "hosts", ["org_id", "last_seen_at"]
    )
    op.create_index(
        "ix_hosts_org_id_vulnerability_count",
        "hosts",
        ["org_id", "vulnerability_count"],
    )

    op.create_table(
        "host_ports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("service", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host_id", "port", "protocol", name="uq_host_ports_host_port_protocol"
        ),
    )
    op.create_index("ix_host_ports_host_id", "host_ports", ["host_id"], unique=False)

    op.create_table(
        "host_findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "host_id", "dedupe_key", name="uq_host_findings_host_dedupe_key"
        ),
    )
    op.create_index(
        "ix_host_findings_host_id", "host_findings", ["host_id"], unique=False
    )
    op.create_index(
        "ix_host_findings_dedupe_key", "host_findings", ["dedupe_key"], unique=False
    )
    op.create_index(
        "ix_host_findings_host_id_fixed_at",
        "host_findings",
        ["host_id", "fixed_at"],
        unique=False,
    )

    for table_name in NEW_TABLES:
        _secure(table_name)


def downgrade() -> None:
    for table_name in NEW_TABLES:
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table_name} FROM dmitri_runtime"
        )
        op.execute(
            f"REVOKE ALL PRIVILEGES ON SEQUENCE public.{table_name}_id_seq "
            f"FROM dmitri_runtime"
        )
    op.drop_table("host_findings")
    op.drop_table("host_ports")
    op.drop_index("ix_hosts_org_id_vulnerability_count", table_name="hosts")
    op.drop_index("ix_hosts_org_id_last_seen_at", table_name="hosts")
    op.drop_constraint(_MACHINE_TYPE_CONSTRAINT, "hosts", type_="check")
    op.drop_column("hosts", "vulnerability_count")
    op.drop_column("hosts", "machine_type")
