from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261012_40"
down_revision = "20261002_39"
branch_labels = None
depends_on = None

TABLE = "deleted_scans"
CHECK = "ck_activity_kind"

DELETABLE_TABLES = (
    "scans",
    "scan_hosts",
    "ports",
    "services",
    "cpes",
    "exposures",
    "industrial_services",
    "modbus_units",
    "findings",
    "risk_snapshots",
    "enrichment_jobs",
    "hosts",
    "commands",
    "ai_scan_analyses",
)

PREVIOUS_KINDS = (
    "scan_started",
    "scan_finished",
    "scan_failed",
    "scan_cancelled",
    "machine_first_seen",
    "role_changed",
    "member_invited",
    "invite_revoked",
    "member_removed",
    "account_deleted",
)
KINDS = (*PREVIOUS_KINDS, "scans_deleted", "machines_deleted")


def _replace_check(kinds: tuple[str, ...]) -> None:
    op.drop_constraint(CHECK, "activity", schema="public", type_="check")
    op.create_check_constraint(
        CHECK,
        "activity",
        "kind IN (" + ", ".join(f"'{kind}'" for kind in kinds) + ")",
        schema="public",
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("scan_id"),
    )
    op.create_index(f"ix_{TABLE}_org_id", TABLE, ["org_id"])
    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM PUBLIC")
    for role in ("anon", "authenticated"):
        op.execute(
            f"DO $$ BEGIN "
            f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
            f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM {role}; "
            "END IF; END $$"
        )
    op.execute(f"GRANT SELECT, INSERT ON TABLE public.{TABLE} TO dmitri_runtime")

    for table in DELETABLE_TABLES:
        op.execute(f"GRANT DELETE ON TABLE public.{table} TO dmitri_runtime")
    op.execute("GRANT UPDATE (scan_id) ON TABLE public.ai_usage TO dmitri_runtime")

    _replace_check(KINDS)


def downgrade() -> None:
    op.execute(
        "DELETE FROM public.activity "
        "WHERE kind IN ('scans_deleted', 'machines_deleted')"
    )
    _replace_check(PREVIOUS_KINDS)

    op.execute("REVOKE UPDATE (scan_id) ON TABLE public.ai_usage FROM dmitri_runtime")
    for table in DELETABLE_TABLES:
        op.execute(f"REVOKE DELETE ON TABLE public.{table} FROM dmitri_runtime")

    op.drop_index(f"ix_{TABLE}_org_id", table_name=TABLE)
    op.drop_table(TABLE)
