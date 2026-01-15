"""Allow agencies slug to be nullable."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_agency_slug_nullable"
down_revision = "0008_remove_proc_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("agencies", "slug", existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE agencies SET slug = CONCAT('agency-', id) WHERE slug IS NULL"))
    op.alter_column("agencies", "slug", existing_type=sa.String(length=100), nullable=False)
