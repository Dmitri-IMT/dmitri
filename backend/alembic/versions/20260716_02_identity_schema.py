from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "20260716_02"
down_revision = "20260715_01"
branch_labels = None
depends_on = None

IDENTITY_TABLES = ("orgs", "users", "invites")


def _qualified(objects: tuple[str, ...]) -> str:
    return ", ".join(f"public.{name}" for name in objects)


def _revoke_supabase_roles() -> None:
    tables = _qualified(IDENTITY_TABLES)
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
        "orgs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
    )
    op.create_index(
        "ix_users_org_email",
        "users",
        ["org_id", sa.text("lower(email)")],
        unique=True,
    )
    op.create_table(
        "invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_invites_role"),
    )
    op.create_index("ix_invites_token_hash", "invites", ["token_hash"], unique=True)

    op.add_column("scans", sa.Column("org_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_scans_org_id_orgs", "scans", "orgs", ["org_id"], ["id"])
    op.create_index("ix_scans_org_id", "scans", ["org_id"], unique=False)

    for table in IDENTITY_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    _revoke_supabase_roles()

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE {_qualified(IDENTITY_TABLES)} "
        "TO dmitri_runtime"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE ALL PRIVILEGES ON TABLE {_qualified(IDENTITY_TABLES)} "
        "FROM dmitri_runtime"
    )
    op.drop_index("ix_scans_org_id", table_name="scans")
    op.drop_constraint("fk_scans_org_id_orgs", "scans", type_="foreignkey")
    op.drop_column("scans", "org_id")
    op.drop_index("ix_invites_token_hash", table_name="invites")
    op.drop_table("invites")
    op.drop_index("ix_users_org_email", table_name="users")
    op.drop_table("users")
    op.drop_table("orgs")
