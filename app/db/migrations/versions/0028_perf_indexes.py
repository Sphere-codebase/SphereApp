"""Performance indexes.

Revision ID: 0028_perf_indexes
Revises: 0027_tenant_hardening_rls
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0028_perf_indexes"
down_revision = "0027_tenant_hardening_rls"
branch_labels = None
depends_on = None


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_claims_clinic_updated_at ON claims (clinic_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_claims_clinic_doctor_updated_at ON claims (clinic_id, doctor_id, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_patients_clinic_last_name ON patients (clinic_id, last_name)",
    "CREATE INDEX IF NOT EXISTS ix_patients_clinic_doctor_id ON patients (clinic_id, doctor_id)",
    "CREATE INDEX IF NOT EXISTS ix_chat_sessions_clinic_doctor_created_at ON chat_sessions (clinic_id, doctor_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_clinic_action_created_at ON audit_logs (clinic_id, action, created_at DESC)",
]

DROP_STATEMENTS = [
    "DROP INDEX IF EXISTS ix_claims_clinic_updated_at",
    "DROP INDEX IF EXISTS ix_claims_clinic_doctor_updated_at",
    "DROP INDEX IF EXISTS ix_patients_clinic_last_name",
    "DROP INDEX IF EXISTS ix_patients_clinic_doctor_id",
    "DROP INDEX IF EXISTS ix_chat_sessions_clinic_doctor_created_at",
    "DROP INDEX IF EXISTS ix_audit_logs_clinic_action_created_at",
]


def upgrade() -> None:
    for statement in INDEX_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DROP_STATEMENTS:
        op.execute(statement)
