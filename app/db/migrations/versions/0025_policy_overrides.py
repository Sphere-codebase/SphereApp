"""Add clinic and doctor policy overrides.

Revision ID: 0025_policy_overrides
Revises: 0024_claims_updated_at
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0025_policy_overrides"
down_revision = "0024_claims_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinic_policy_overrides",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("clinic_id", sa.BigInteger(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column(
            "policy_link_id",
            sa.BigInteger(),
            sa.ForeignKey("policy_links.id"),
            nullable=False,
        ),
        sa.Column("override_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index(
        "ix_clinic_policy_overrides_clinic_id",
        "clinic_policy_overrides",
        ["clinic_id"],
    )
    op.create_index(
        "ix_clinic_policy_overrides_policy_link_id",
        "clinic_policy_overrides",
        ["policy_link_id"],
    )
    op.create_index(
        "uq_clinic_policy_overrides_clinic_id_policy_link_id",
        "clinic_policy_overrides",
        ["clinic_id", "policy_link_id"],
        unique=True,
    )

    op.create_table(
        "doctor_policy_overrides",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("doctor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column(
            "policy_link_id",
            sa.BigInteger(),
            sa.ForeignKey("policy_links.id"),
            nullable=False,
        ),
        sa.Column("override_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index(
        "ix_doctor_policy_overrides_doctor_id",
        "doctor_policy_overrides",
        ["doctor_id"],
    )
    op.create_index(
        "ix_doctor_policy_overrides_clinic_id",
        "doctor_policy_overrides",
        ["clinic_id"],
    )
    op.create_index(
        "ix_doctor_policy_overrides_policy_link_id",
        "doctor_policy_overrides",
        ["policy_link_id"],
    )
    op.create_index(
        "uq_doctor_policy_overrides_doctor_id_policy_link_id",
        "doctor_policy_overrides",
        ["doctor_id", "policy_link_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_doctor_policy_overrides_doctor_id_policy_link_id",
        table_name="doctor_policy_overrides",
    )
    op.drop_index(
        "ix_doctor_policy_overrides_policy_link_id",
        table_name="doctor_policy_overrides",
    )
    op.drop_index(
        "ix_doctor_policy_overrides_clinic_id",
        table_name="doctor_policy_overrides",
    )
    op.drop_index(
        "ix_doctor_policy_overrides_doctor_id",
        table_name="doctor_policy_overrides",
    )
    op.drop_table("doctor_policy_overrides")

    op.drop_index(
        "uq_clinic_policy_overrides_clinic_id_policy_link_id",
        table_name="clinic_policy_overrides",
    )
    op.drop_index(
        "ix_clinic_policy_overrides_policy_link_id",
        table_name="clinic_policy_overrides",
    )
    op.drop_index(
        "ix_clinic_policy_overrides_clinic_id",
        table_name="clinic_policy_overrides",
    )
    op.drop_table("clinic_policy_overrides")
