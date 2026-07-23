from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260722_05"
down_revision = "20260722_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("identity_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mac", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("hostname", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("vendor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("open_ports_count", sa.Integer(), nullable=False),
        sa.Column(
            "highest_severity", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hosts_org_id", "hosts", ["org_id"], unique=False)
    op.create_index("ix_hosts_identity_key", "hosts", ["identity_key"], unique=False)
    op.create_index(
        "uq_hosts_org_identity",
        "hosts",
        ["org_id", "identity_key"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    op.add_column("scan_hosts", sa.Column("host_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_scan_hosts_host_id_hosts", "scan_hosts", "hosts", ["host_id"], ["id"]
    )
    op.create_index(
        "ix_scan_hosts_host_id", "scan_hosts", ["host_id"], unique=False
    )

    op.execute("ALTER TABLE public.hosts ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.hosts FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.hosts FROM authenticated;
            END IF;
        END
        $$
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON hosts TO dmitri_runtime")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.hosts FROM dmitri_runtime")
    op.drop_index("ix_scan_hosts_host_id", table_name="scan_hosts")
    op.drop_constraint(
        "fk_scan_hosts_host_id_hosts", "scan_hosts", type_="foreignkey"
    )
    op.drop_column("scan_hosts", "host_id")
    op.drop_table("hosts")
