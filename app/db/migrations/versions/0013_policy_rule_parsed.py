"""Add parsed policy rule fields and index."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_policy_rule_parsed"
down_revision = "0012_contract_drop_old_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policy_rules", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("policy_rules", sa.Column("next_review_iso", sa.Date(), nullable=True))
    op.add_column(
        "policy_rules",
        sa.Column("criteria_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "policy_rules",
        sa.Column("notes_json", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_policy_rules_policy_link_id_extracted_at",
        "policy_rules",
        ["policy_link_id", "extracted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_policy_rules_policy_link_id_extracted_at",
        table_name="policy_rules",
    )
    op.drop_column("policy_rules", "notes_json")
    op.drop_column("policy_rules", "criteria_json")
    op.drop_column("policy_rules", "next_review_iso")
    op.drop_column("policy_rules", "title")
