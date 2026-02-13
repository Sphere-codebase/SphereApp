"""Create addresses and clinics tables.

Revision ID: 0015_addresses_clinics
Revises: 0014_claim_line_cov_id
Create Date: 2026-02-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0015_addresses_clinics"
down_revision = "0014_claim_line_cov_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("line1", sa.String(), nullable=False),
        sa.Column("line2", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("zip", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
    )

    op.create_table(
        "clinics",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address_id", sa.BigInteger(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["address_id"], ["addresses.id"]),
    )
    op.create_index("ix_clinics_address_id", "clinics", ["address_id"])


def downgrade() -> None:
    op.drop_index("ix_clinics_address_id", table_name="clinics")
    op.drop_table("clinics")
    op.drop_table("addresses")
