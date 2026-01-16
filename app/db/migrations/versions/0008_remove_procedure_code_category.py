"""Remove procedure code category column."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_remove_proc_category"
down_revision = "0007_tenant_scoped_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("procedure_codes", "category")


def downgrade() -> None:
    op.add_column(
        "procedure_codes",
        sa.Column("category", sa.String(length=255), nullable=True),
    )
