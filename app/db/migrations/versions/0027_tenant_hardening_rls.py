"""Tenant hardening: RLS + clinic block index.

Revision ID: 0027_tenant_hardening_rls
Revises: 0026_clinics_is_blocked
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_tenant_hardening_rls"
down_revision = "0026_clinics_is_blocked"
branch_labels = None
depends_on = None


TABLES = [
    "patients",
    "claims",
    "chat_sessions",
    "chat_messages",
    "claim_line_coverage",
    "claim_procedure_facts",
    "audit_logs",
]


POLICY_TEMPLATE = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = '{table_name}'
          AND policyname = '{policy_name}'
    ) THEN
        CREATE POLICY {policy_name}
        ON {table_name}
        USING (
            current_setting('app.is_platform_admin', true) = 'true'
            OR clinic_id = NULLIF(current_setting('app.current_clinic_id', true), '')::bigint
        )
        WITH CHECK (
            current_setting('app.is_platform_admin', true) = 'true'
            OR clinic_id = NULLIF(current_setting('app.current_clinic_id', true), '')::bigint
        );
    END IF;
END $$;
"""


def upgrade() -> None:
    op.create_index("ix_clinics_is_blocked", "clinics", ["is_blocked"], unique=False)

    for table_name in TABLES:
        policy_name = f"rls_{table_name}_clinic"
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(POLICY_TEMPLATE.format(table_name=table_name, policy_name=policy_name))


def downgrade() -> None:
    for table_name in TABLES:
        policy_name = f"rls_{table_name}_clinic"
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name};")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_clinics_is_blocked", table_name="clinics")
