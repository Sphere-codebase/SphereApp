"""Add is_blocked to clinics.

Revision ID: 0026_clinics_is_blocked
Revises: 0025_policy_overrides
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0026_clinics_is_blocked"
down_revision = "0025_policy_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("clinics", "is_blocked")
