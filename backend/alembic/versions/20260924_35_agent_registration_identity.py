"""Make registration retries return one device per organization and key."""

from alembic import op

revision = "20260924_35"
down_revision = "20260922_34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing duplicates must be resolved by the operator, not silently
    # deleted: either row may own scans, commands, or a revoked identity.
    op.create_unique_constraint(
        "uq_agents_org_public_key", "agents", ["org_id", "public_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_agents_org_public_key", "agents", type_="unique")
