from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260915_27"
down_revision = "20260912_26"
branch_labels = None
depends_on = None

TABLE = "exposures"

_MACHINE_TYPES = (
    "'router', 'computer', 'camera', 'storage', 'tv', "
    "'phone', 'printer', 'sensor', 'unknown'"
)
_ROLES = (
    "'administration', 'data_store', 'file_sharing', 'remote_access', "
    "'proxy', 'api', 'device_control', 'discovery', 'media', "
    "'general_service', 'unknown'"
)


def _revoke_data_api_roles() -> None:
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
    op.add_column(
        "scans",
        sa.Column(
            "assessment_policy_version",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )
    op.add_column(
        "scan_hosts",
        sa.Column("machine_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "scan_hosts",
        sa.Column("device_profile_json", postgresql.JSONB(), nullable=True),
    )
    op.create_check_constraint(
        "ck_scan_hosts_machine_type",
        "scan_hosts",
        f"machine_type IS NULL OR machine_type IN ({_MACHINE_TYPES})",
    )
    op.add_column(
        "hosts",
        sa.Column("device_profile_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "hosts",
        sa.Column(
            "device_profile_policy_version",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exposure_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("scan_host_id", sa.Integer(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=False),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "observed_service", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "observed_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attention", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.scan_id"], name="fk_exposures_scan_id_scans"
        ),
        sa.ForeignKeyConstraint(
            ["scan_host_id"],
            ["scan_hosts.id"],
            name="fk_exposures_scan_host_id_scan_hosts",
        ),
        sa.ForeignKeyConstraint(
            ["port_id"], ["ports.id"], name="fk_exposures_port_id_ports"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exposure_id", name="uq_exposures_exposure_id"),
        sa.UniqueConstraint(
            "scan_id",
            "scan_host_id",
            "port",
            "protocol",
            name="uq_exposures_scan_host_port_protocol",
        ),
        sa.CheckConstraint(
            f"role IN ({_ROLES})",
            name="ck_exposures_role",
        ),
        sa.CheckConstraint(
            "attention IN ('informational', 'review', 'priority')",
            name="ck_exposures_attention",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_exposures_confidence",
        ),
    )
    for column in ("scan_id", "scan_host_id", "port_id", "role", "attention"):
        op.create_index(
            f"ix_exposures_{column}", TABLE, [column], unique=False
        )

    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")
    _revoke_data_api_roles()
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
    op.execute(
        f"REVOKE ALL PRIVILEGES ON SEQUENCE public.{TABLE}_id_seq "
        "FROM dmitri_runtime"
    )
    op.drop_table(TABLE)

    op.drop_column("hosts", "device_profile_policy_version")
    op.drop_column("hosts", "device_profile_json")
    op.drop_constraint(
        "ck_scan_hosts_machine_type", "scan_hosts", type_="check"
    )
    op.drop_column("scan_hosts", "device_profile_json")
    op.drop_column("scan_hosts", "machine_type")
    op.drop_column("scans", "assessment_policy_version")
