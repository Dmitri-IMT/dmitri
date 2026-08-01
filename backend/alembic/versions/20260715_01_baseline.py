from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260715_01"
down_revision = None
branch_labels = None
depends_on = None

APPLICATION_TABLES = (
    "scans",
    "artifacts",
    "devices",
    "ports",
    "services",
    "cpes",
    "findings",
    "enrichment_jobs",
    "nvd_cache",
    "kev_records",
    "epss_records",
    "kev_cache",
    "epss_cache",
    "risk_snapshots",
)

APPLICATION_SEQUENCES = (
    "artifacts_id_seq",
    "devices_id_seq",
    "ports_id_seq",
    "services_id_seq",
    "cpes_id_seq",
    "findings_id_seq",
    "enrichment_jobs_id_seq",
    "nvd_cache_id_seq",
    "risk_snapshots_id_seq",
)


def _qualified(objects: tuple[str, ...]) -> str:
    return ", ".join(f"public.{name}" for name in objects)


def _revoke_supabase_roles() -> None:
    tables = _qualified(APPLICATION_TABLES)
    sequences = _qualified(APPLICATION_SEQUENCES)
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {tables} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE {sequences} FROM {role};
                END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("subnet", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("scan_profile", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("scan_id"),
    )
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
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mac", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("hostname", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("vendor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "ip"),
    )
    op.create_index("ix_devices_ip", "devices", ["ip"], unique=False)
    op.create_index("ix_devices_scan_id", "devices", ["scan_id"], unique=False)
    op.create_table(
        "ports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "port", "protocol"),
    )
    op.create_index("ix_ports_device_id", "ports", ["device_id"], unique=False)
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("port_id"),
    )
    op.create_index("ix_services_port_id", "services", ["port_id"], unique=False)
    op.create_table(
        "cpes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=False),
        sa.Column("cpe", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("port_id", "cpe"),
    )
    op.create_index("ix_cpes_cpe", "cpes", ["cpe"], unique=False)
    op.create_index("ix_cpes_port_id", "cpes", ["port_id"], unique=False)
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("port_id", sa.Integer(), nullable=True),
        sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("protocol", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("service", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("source_script", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("severity", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("confidence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("recommendation", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("evidence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("references_json", sa.JSON(), nullable=True),
        sa.Column("source_labels_json", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "dedupe_key"),
    )
    op.create_index("ix_findings_confidence", "findings", ["confidence"], unique=False)
    op.create_index("ix_findings_cve_id", "findings", ["cve_id"], unique=False)
    op.create_index("ix_findings_dedupe_key", "findings", ["dedupe_key"], unique=False)
    op.create_index("ix_findings_device_id", "findings", ["device_id"], unique=False)
    op.create_index("ix_findings_ip", "findings", ["ip"], unique=False)
    op.create_index("ix_findings_port_id", "findings", ["port_id"], unique=False)
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"], unique=False)
    op.create_table(
        "enrichment_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("port_id", sa.Integer(), nullable=True),
        sa.Column("finding_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("target_value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
        sa.ForeignKeyConstraint(["port_id"], ["ports.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.scan_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_enrichment_jobs_job_type", "enrichment_jobs", ["job_type"], unique=False
    )
    op.create_index(
        "ix_enrichment_jobs_scan_id", "enrichment_jobs", ["scan_id"], unique=False
    )
    op.create_index(
        "ix_enrichment_jobs_status", "enrichment_jobs", ["status"], unique=False
    )
    op.create_index(
        "ix_enrichment_jobs_target_value",
        "enrichment_jobs",
        ["target_value"],
        unique=False,
    )
    op.create_table(
        "nvd_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("query_kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("query_value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nvd_cache_expires_at", "nvd_cache", ["expires_at"], unique=False
    )
    op.create_index("ix_nvd_cache_query_key", "nvd_cache", ["query_key"], unique=True)
    op.create_index(
        "ix_nvd_cache_query_kind", "nvd_cache", ["query_kind"], unique=False
    )
    op.create_table(
        "kev_records",
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("date_added", sa.DateTime(), nullable=True),
        sa.Column("known_ransomware", sa.Boolean(), nullable=False),
        sa.Column("required_action", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_table(
        "epss_records",
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("epss_score", sa.Float(), nullable=False),
        sa.Column("percentile", sa.Float(), nullable=True),
        sa.Column("scored_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_table(
        "kev_cache",
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_index(
        "ix_kev_cache_expires_at", "kev_cache", ["expires_at"], unique=False
    )
    op.create_table(
        "epss_cache",
        sa.Column("cve_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("cve_id"),
    )
    op.create_index(
        "ix_epss_cache_expires_at", "epss_cache", ["expires_at"], unique=False
    )
    op.create_table(
        "risk_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("finding_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("exploitability", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("rationale", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id"),
    )
    op.create_index(
        "ix_risk_snapshots_finding_id",
        "risk_snapshots",
        ["finding_id"],
        unique=False,
    )

    for table in APPLICATION_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    _revoke_supabase_roles()

    # dmitri_runtime is a cluster-wide role, not a per-database object, so a
    # plain CREATE ROLE fails whenever this baseline is replayed against a
    # cluster another database already provisioned — which is every upgrade
    # after the first in a shared test/CI Postgres. Guarded here rather than in
    # a later revision: the role must exist before the GRANTs below.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_roles "
        "WHERE rolname = 'dmitri_runtime') THEN "
        "CREATE ROLE dmitri_runtime WITH LOGIN PASSWORD NULL BYPASSRLS "
        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION; "
        "END IF; END $$"
    )
    op.execute(
        "DO $$ BEGIN EXECUTE format("
        "'GRANT CONNECT ON DATABASE %I TO dmitri_runtime', current_database()); END $$"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO dmitri_runtime")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {_qualified(APPLICATION_TABLES)} "
        "TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE {_qualified(APPLICATION_SEQUENCES)} "
        "TO dmitri_runtime"
    )


def downgrade() -> None:
    op.drop_table("risk_snapshots")
    op.drop_table("enrichment_jobs")
    op.drop_table("findings")
    op.drop_table("cpes")
    op.drop_table("services")
    op.drop_table("ports")
    op.drop_table("devices")
    op.drop_table("artifacts")
    op.drop_table("scans")
    op.drop_table("epss_cache")
    op.drop_table("kev_cache")
    op.drop_table("epss_records")
    op.drop_table("kev_records")
    op.drop_table("nvd_cache")

    op.execute("REVOKE USAGE ON SCHEMA public FROM dmitri_runtime")
    op.execute(
        "DO $$ BEGIN EXECUTE format("
        "'REVOKE CONNECT ON DATABASE %I FROM dmitri_runtime', "
        "current_database()); END $$"
    )
    # Mirror of the guarded CREATE above: another database in the same cluster
    # may still grant to this role, and dropping it out from under them would
    # break them. Only that specific error is swallowed — anything else still
    # fails the downgrade.
    op.execute(
        "DO $$ BEGIN DROP ROLE dmitri_runtime; "
        "EXCEPTION WHEN dependent_objects_still_exist THEN NULL; END $$"
    )
