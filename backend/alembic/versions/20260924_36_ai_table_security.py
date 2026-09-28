"""Apply the existing backend-only access policy to the two newer AI tables."""

from alembic import op

revision = "20260924_36"
down_revision = "20260924_35"
branch_labels = None
depends_on = None

TABLES = ("ai_chat_messages", "ai_usage")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN "
                f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
                f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM {role}; "
                "END IF; END $$"
            )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
