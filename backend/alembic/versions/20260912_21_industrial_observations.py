from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260912_21"
down_revision = "20260912_20"
branch_labels = None
depends_on = None

INDUSTRIAL_SERVICES = "industrial_services"
MODBUS_UNITS = "modbus_units"

INDUSTRIAL_PROTOCOLS = ("modbus_tcp",)
INDUSTRIAL_CONFIDENCE = ("suspected", "confirmed")
MODBUS_UNIT_STATUSES = (
    "responding",
    "exception",
    "timeout",
    "error",
    "skipped",
)


def _revoke_supabase_roles(table: str) -> None:
    qualified = f"public.{table}"
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {qualified} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE public.{table}_id_seq FROM {role};
                END IF;
            END
            $$
            """
        )


def _grant_runtime(table: str) -> None:
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE public.{table}_id_seq TO dmitri_runtime"
    )


def upgrade() -> None:
    op.create_table(
        INDUSTRIAL_SERVICES,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_host_id", sa.Integer(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=True),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("confidence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mapping_source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("evidence_sources_json", postgresql.JSONB(), nullable=False),
        sa.Column("write_requests_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_host_id"], ["scan_hosts.id"]),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scan_host_id",
            "protocol",
            "port",
            name="uq_industrial_services_scan_host_protocol_port",
        ),
        sa.CheckConstraint(
            "protocol IN (" + ", ".join(f"'{p}'" for p in INDUSTRIAL_PROTOCOLS) + ")",
            name="ck_industrial_services_protocol",
        ),
        sa.CheckConstraint(
            "confidence IN ("
            + ", ".join(f"'{c}'" for c in INDUSTRIAL_CONFIDENCE)
            + ")",
            name="ck_industrial_services_confidence",
        ),
    )
    op.create_index(
        "ix_industrial_services_scan_host_id",
        INDUSTRIAL_SERVICES,
        ["scan_host_id"],
        unique=False,
    )
    op.create_index(
        "ix_industrial_services_port_id",
        INDUSTRIAL_SERVICES,
        ["port_id"],
        unique=False,
    )

    op.create_table(
        MODBUS_UNITS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("industrial_service_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("exception_code", sa.Integer(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("identification_json", postgresql.JSONB(), nullable=True),
        sa.Column("identification_sources_json", postgresql.JSONB(), nullable=False),
        sa.Column("address_ranges_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["industrial_service_id"], ["industrial_services.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "industrial_service_id",
            "unit_id",
            name="uq_modbus_units_industrial_service_unit_id",
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in MODBUS_UNIT_STATUSES) + ")",
            name="ck_modbus_units_status",
        ),
    )
    op.create_index(
        "ix_modbus_units_industrial_service_id",
        MODBUS_UNITS,
        ["industrial_service_id"],
        unique=False,
    )

    op.add_column(
        "findings",
        sa.Column("modbus_unit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_findings_modbus_unit_id_modbus_units",
        "findings",
        "modbus_units",
        ["modbus_unit_id"],
        ["id"],
    )
    op.create_index(
        "ix_findings_modbus_unit_id",
        "findings",
        ["modbus_unit_id"],
        unique=False,
    )

    op.add_column(
        "orgs",
        sa.Column("ot_digest_key", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    for table in (INDUSTRIAL_SERVICES, MODBUS_UNITS):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        _revoke_supabase_roles(table)
        _grant_runtime(table)


def downgrade() -> None:
    for table in (INDUSTRIAL_SERVICES, MODBUS_UNITS):
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM dmitri_runtime")
        op.execute(
            f"REVOKE ALL PRIVILEGES ON SEQUENCE public.{table}_id_seq "
            "FROM dmitri_runtime"
        )

    op.drop_index("ix_findings_modbus_unit_id", table_name="findings")
    op.drop_constraint(
        "fk_findings_modbus_unit_id_modbus_units",
        "findings",
        type_="foreignkey",
    )
    op.drop_column("findings", "modbus_unit_id")

    op.drop_column("orgs", "ot_digest_key")

    op.drop_index("ix_modbus_units_industrial_service_id", table_name=MODBUS_UNITS)
    op.drop_table(MODBUS_UNITS)

    op.drop_index("ix_industrial_services_port_id", table_name=INDUSTRIAL_SERVICES)
    op.drop_index("ix_industrial_services_scan_host_id", table_name=INDUSTRIAL_SERVICES)
    op.drop_table(INDUSTRIAL_SERVICES)
