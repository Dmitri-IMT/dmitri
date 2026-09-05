from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260905_19"
down_revision = "20260904_18"
branch_labels = None
depends_on = None

TABLE = "activity"

KINDS = (
    "scan_started",
    "scan_finished",
    "scan_failed",
    "machine_first_seen",
    "role_changed",
    "member_invited",
    "invite_revoked",
    "member_removed",
    "account_deleted",
)

UNIQUE_KINDS = (
    "scan_started",
    "scan_finished",
    "scan_failed",
    "machine_first_seen",
    "member_invited",
    "invite_revoked",
)


def _revoke_supabase_roles() -> None:
    table = f"public.{TABLE}"
    for role in ("anon", "authenticated"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL PRIVILEGES ON TABLE {table} FROM {role};
                    REVOKE ALL PRIVILEGES ON SEQUENCE public.{TABLE}_id_seq FROM {role};
                END IF;
            END
            $$
            """
        )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN (" + ", ".join(f"'{k}'" for k in KINDS) + ")",
            name="ck_activity_kind",
        ),
    )
    op.create_index("ix_activity_org_id", TABLE, ["org_id"], unique=False)
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_activity_org_kind_subject
        ON public.{TABLE} (org_id, kind, subject_id)
        WHERE subject_id IS NOT NULL
          AND kind IN ({", ".join(f"'{k}'" for k in UNIQUE_KINDS)})
        """
    )
    op.execute(
        f"""
        CREATE INDEX ix_activity_org_id_occurred_at_id
        ON public.{TABLE} (org_id, occurred_at DESC, id DESC)
        """
    )

    op.execute(f"ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY")

    _revoke_supabase_roles()

    op.execute(
        f"GRANT SELECT, INSERT ON TABLE public.{TABLE} TO dmitri_runtime"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON SEQUENCE public.{TABLE}_id_seq TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM dmitri_runtime")
    op.execute("DROP INDEX IF EXISTS ix_activity_org_id_occurred_at_id")
    op.execute("DROP INDEX IF EXISTS uq_activity_org_kind_subject")
    op.drop_index("ix_activity_org_id", table_name=TABLE)
    op.drop_table(TABLE)
