from __future__ import annotations

from alembic import op

revision = "20260927_37"
down_revision = "20260924_36"
branch_labels = None
depends_on = None

TABLE = "activity"
INDEX = "uq_activity_org_kind_subject"
CHECK = "ck_activity_kind"

KINDS = (
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

UNIQUE_KINDS = (
    "scan_started",
    "scan_finished",
    "scan_failed",
    "scan_cancelled",
    "machine_first_seen",
    "member_invited",
    "invite_revoked",
)

PREVIOUS_KINDS = tuple(kind for kind in KINDS if kind != "scan_cancelled")
PREVIOUS_UNIQUE_KINDS = tuple(
    kind for kind in UNIQUE_KINDS if kind != "scan_cancelled"
)


def _replace_check(kinds: tuple[str, ...]) -> None:
    op.drop_constraint(CHECK, TABLE, schema="public", type_="check")
    op.create_check_constraint(
        CHECK,
        TABLE,
        "kind IN (" + ", ".join(f"'{kind}'" for kind in kinds) + ")",
        schema="public",
    )


def _replace_unique_index(kinds: tuple[str, ...]) -> None:
    op.execute(f"DROP INDEX IF EXISTS public.{INDEX}")
    op.execute(
        f"CREATE UNIQUE INDEX {INDEX} "
        f"ON public.{TABLE} (org_id, kind, subject_id) "
        f"WHERE subject_id IS NOT NULL "
        f"AND kind IN ({', '.join(f'{kind!r}' for kind in kinds)})"
    )


def upgrade() -> None:
    _replace_check(KINDS)
    _replace_unique_index(UNIQUE_KINDS)


def downgrade() -> None:
    op.execute("DELETE FROM public.activity WHERE kind = 'scan_cancelled'")
    _replace_check(PREVIOUS_KINDS)
    _replace_unique_index(PREVIOUS_UNIQUE_KINDS)
