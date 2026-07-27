from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260724_11"
down_revision = "20260724_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("agents", "secret_ciphertext")
    op.drop_column("agents", "secret_nonce")
    op.drop_column("agents", "secret_key_version")
    op.add_column(
        "agents", sa.Column("public_key", sa.LargeBinary(), nullable=False)
    )


def downgrade() -> None:
    # Knowingly lossy if the agents table holds rows: public_key has no
    # ciphertext/nonce/key_version to reconstruct from, so downgraded rows
    # would violate the re-added NOT NULL constraints. Safe only because the
    # table is empty at every revision this migration is expected to run in.
    op.drop_column("agents", "public_key")
    op.add_column(
        "agents", sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False)
    )
    op.add_column(
        "agents", sa.Column("secret_nonce", sa.LargeBinary(), nullable=False)
    )
    op.add_column(
        "agents", sa.Column("secret_key_version", sa.Integer(), nullable=False)
    )
