"""Create patient insurance policies table.

Revision ID: 0018_patient_insurance_policies
Revises: 0017_patients_clinic_fields
Create Date: 2026-02-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_patient_insurance_policies"
down_revision = "0017_patients_clinic_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_insurance_policies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("member_id", sa.String(), nullable=True),
        sa.Column("policy_type", sa.String(), nullable=True),
        sa.Column("copay_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("deductible_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint(
            "priority IN ('primary', 'secondary')",
            name="ck_patient_insurance_policies_priority",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
    )
    op.create_index(
        "ix_patient_insurance_policies_clinic_id_patient_id",
        "patient_insurance_policies",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "uq_patient_insurance_policies_patient_id_priority",
        "patient_insurance_policies",
        ["patient_id", "priority"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_patient_insurance_policies_patient_id_priority",
        table_name="patient_insurance_policies",
    )
    op.drop_index(
        "ix_patient_insurance_policies_clinic_id_patient_id",
        table_name="patient_insurance_policies",
    )
    op.drop_table("patient_insurance_policies")
