"""Add admin fields to users."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_add_user_admin_fields"
down_revision = "0002_claim_event_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("users", "is_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_admin")
    op.drop_column("users", "full_name")
