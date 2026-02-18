"""Add role field to users.

Revision ID: 0021_users_role_field
Revises: 0020_clinic_scoped_records
Create Date: 2026-02-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0021_users_role_field"
down_revision = "0020_clinic_scoped_records"
branch_labels = None
depends_on = None


ROLE_CHECK = "role IN ('doctor', 'chief_doctor', 'clinic_admin', 'platform_staff_admin')"


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(), nullable=True))
    op.create_check_constraint("ck_users_role", "users", ROLE_CHECK)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET role = CASE "
            "WHEN EXISTS ("
            "SELECT 1 FROM user_roles ur "
            "JOIN roles r ON ur.role_id = r.id "
            "WHERE ur.user_id = users.id AND r.code IN ('platform_staff_admin', 'admin')"
            ") THEN 'platform_staff_admin' "
            "WHEN EXISTS ("
            "SELECT 1 FROM user_roles ur "
            "JOIN roles r ON ur.role_id = r.id "
            "WHERE ur.user_id = users.id AND r.code = 'clinic_admin'"
            ") THEN 'clinic_admin' "
            "WHEN EXISTS ("
            "SELECT 1 FROM user_roles ur "
            "JOIN roles r ON ur.role_id = r.id "
            "WHERE ur.user_id = users.id AND r.code = 'chief_doctor'"
            ") THEN 'chief_doctor' "
            "ELSE 'doctor' END "
            "WHERE role IS NULL"
        )
    )

    op.alter_column(
        "users",
        "role",
        nullable=False,
        server_default=sa.text("'doctor'"),
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
