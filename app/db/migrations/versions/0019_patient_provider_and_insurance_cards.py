"""Add provider_name and insurance card metadata.

Revision ID: 0019_patient_cards
Revises: 0018_patient_insurance_policies
Create Date: 2026-02-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0019_patient_cards"
down_revision = "0018_patient_insurance_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("provider_name", sa.String(), nullable=True))

    op.create_table(
        "insurance_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["policy_id"], ["patient_insurance_policies.id"]),
    )
    op.create_index(
        "ix_insurance_cards_policy_id_side",
        "insurance_cards",
        ["policy_id", "side"],
    )


def downgrade() -> None:
    op.drop_index("ix_insurance_cards_policy_id_side", table_name="insurance_cards")
    op.drop_table("insurance_cards")
    op.drop_column("patients", "provider_name")
