"""Add updated_at to claims.

Revision ID: 0024_claims_updated_at
Revises: 0023_chat_workspace_sessions
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0024_claims_updated_at"
down_revision = "0023_chat_workspace_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("claims", "updated_at")
