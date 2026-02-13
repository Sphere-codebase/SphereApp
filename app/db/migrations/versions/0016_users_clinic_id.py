"""Add clinic_id to users and backfill.

Revision ID: 0016_users_clinic_id
Revises: 0015_addresses_clinics
Create Date: 2026-02-13
"""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_users_clinic_id"
down_revision = "0015_addresses_clinics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("clinic_id", sa.BigInteger(), nullable=True))

    bind = op.get_bind()
    default_clinic_id = 1
    now = datetime.utcnow()
    existing = bind.execute(
        sa.text("SELECT id FROM clinics WHERE id = :id"),
        {"id": default_clinic_id},
    ).fetchone()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO clinics (id, name, created_at, updated_at) "
                "VALUES (:id, :name, :created_at, :updated_at)"
            ),
            {
                "id": default_clinic_id,
                "name": "Default Clinic",
                "created_at": now,
                "updated_at": now,
            },
        )

    bind.execute(
        sa.text("UPDATE users SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    op.create_foreign_key(
        "fk_users_clinic_id_clinics",
        "users",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.alter_column(
        "users",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_clinic_id_clinics", "users", type_="foreignkey")
    op.drop_column("users", "clinic_id")
