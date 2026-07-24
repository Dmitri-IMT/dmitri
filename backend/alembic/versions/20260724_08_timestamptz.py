"""Convert naive timestamp columns to timestamptz.

Every datetime the application writes comes from ``utc_now()``, which is
timezone-aware, but these columns were created as ``TIMESTAMP WITHOUT TIME ZONE``.
psycopg returns naive datetimes from such columns, so comparing a stored value
against ``utc_now()`` raises::

    TypeError: can't compare offset-naive and offset-aware datetimes

That broke refresh-token and password-reset expiry outright (the session tables
were created aware in 20260722_07) and still affects the cache expiry checks in
``services/{epss,kev,nvd}.py`` and the host first/last-seen round trip.

Stored values are already UTC instants, so the conversion is a pure
reinterpretation: ``AT TIME ZONE 'UTC'``. No data changes.
"""

from __future__ import annotations

from alembic import op

revision = "20260724_08"
down_revision = "20260722_07"
branch_labels = None
depends_on = None

NAIVE_TIMESTAMP_COLUMNS = {
    "enrichment_jobs": ("created_at", "started_at", "completed_at"),
    "epss_cache": ("fetched_at", "expires_at"),
    "epss_records": ("scored_at", "fetched_at", "updated_at"),
    "findings": ("created_at", "updated_at"),
    "hosts": ("first_seen_at", "last_seen_at", "created_at", "updated_at"),
    "invites": ("expires_at", "consumed_at", "created_at"),
    "kev_cache": ("fetched_at", "expires_at"),
    "kev_records": ("date_added", "fetched_at", "updated_at"),
    "nvd_cache": ("fetched_at", "expires_at"),
    "orgs": ("created_at",),
    "ports": ("created_at",),
    "risk_snapshots": ("created_at", "updated_at"),
    "scan_hosts": ("created_at",),
    "scans": ("timestamp", "created_at"),
    "users": ("password_changed_at", "created_at"),
}


def _retype(target: str) -> None:
    for table, columns in NAIVE_TIMESTAMP_COLUMNS.items():
        for column in columns:
            op.execute(
                f"ALTER TABLE public.{table} ALTER COLUMN {column} "
                f"TYPE {target} USING {column} AT TIME ZONE 'UTC'"
            )


def upgrade() -> None:
    _retype("timestamptz")


def downgrade() -> None:
    _retype("timestamp")
