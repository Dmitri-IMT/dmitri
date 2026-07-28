from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260727_12"
down_revision = "20260724_11"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_findings_severity"
# Spelled out rather than imported from api.schemas.read: a revision is a frozen
# historical snapshot, so its SQL must not shift when the live domain is edited.
# test_finding_severity_migration.py asserts the two still agree.
_ALLOWED = "'low', 'medium', 'high', 'critical'"
_CHECK = f"severity IN ({_ALLOWED})"


def upgrade() -> None:
    bind = op.get_bind()
    bad = bind.execute(
        sa.text(
            f"SELECT DISTINCT severity FROM findings "
            f"WHERE severity NOT IN ({_ALLOWED})"
        )
    ).fetchall()
    if bad:
        values = ", ".join(repr(row[0]) for row in bad)
        raise RuntimeError(f"findings.severity out of domain: {values}")
    op.create_check_constraint(_CONSTRAINT, "findings", _CHECK)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "findings", type_="check")
