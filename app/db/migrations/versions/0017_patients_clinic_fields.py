"""Add clinic/address and demographic fields to patients.

Revision ID: 0017_patients_clinic_fields
Revises: 0016_users_clinic_id
Create Date: 2026-02-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0017_patients_clinic_fields"
down_revision = "0016_users_clinic_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("clinic_id", sa.BigInteger(), nullable=True))
    op.add_column("patients", sa.Column("address_id", sa.BigInteger(), nullable=True))
    op.add_column("patients", sa.Column("chart_number", sa.String(), nullable=True))
    op.add_column("patients", sa.Column("gender", sa.String(), nullable=True))
    op.add_column("patients", sa.Column("primary_phone", sa.String(), nullable=True))
    op.add_column("patients", sa.Column("secondary_phone", sa.String(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE patients "
            "SET clinic_id = users.clinic_id "
            "FROM users "
            "WHERE patients.doctor_id = users.id AND patients.clinic_id IS NULL"
        )
    )

    default_clinic_id = 1
    bind.execute(
        sa.text("UPDATE patients SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    op.create_foreign_key(
        "fk_patients_clinic_id_clinics",
        "patients",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_patients_address_id_addresses",
        "patients",
        "addresses",
        ["address_id"],
        ["id"],
    )
    op.alter_column(
        "patients",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )


def downgrade() -> None:
    op.drop_constraint("fk_patients_address_id_addresses", "patients", type_="foreignkey")
    op.drop_constraint("fk_patients_clinic_id_clinics", "patients", type_="foreignkey")
    op.drop_column("patients", "secondary_phone")
    op.drop_column("patients", "primary_phone")
    op.drop_column("patients", "gender")
    op.drop_column("patients", "chart_number")
    op.drop_column("patients", "address_id")
    op.drop_column("patients", "clinic_id")
