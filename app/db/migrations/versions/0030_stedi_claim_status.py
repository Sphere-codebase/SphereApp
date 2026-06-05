"""Stedi claim status integration.

Revision ID: 0030_stedi_claim_status
Revises: 0029_virtual_claim_checklists
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0030_stedi_claim_status"
down_revision = "0029_virtual_claim_checklists"
branch_labels = None
depends_on = None


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
    op.add_column(
        "insurance_companies",
        sa.Column("stedi_trading_partner_service_id", sa.String(), nullable=True),
    )
    op.add_column("clinics", sa.Column("billing_provider_npi", sa.String(), nullable=True))
    op.add_column("clinics", sa.Column("billing_provider_tax_id", sa.String(), nullable=True))
    op.add_column(
        "clinics",
        sa.Column("billing_provider_organization_name", sa.String(), nullable=True),
    )

    op.add_column("claims", sa.Column("stedi_status", sa.String(), nullable=True))
    op.add_column("claims", sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("claims", sa.Column("stedi_status_code", sa.String(), nullable=True))
    op.add_column("claims", sa.Column("stedi_status_category", sa.String(), nullable=True))
    op.add_column("claims", sa.Column("stedi_status_message", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("stedi_amount_paid", sa.Numeric(), nullable=True))
    op.add_column(
        "claims", sa.Column("stedi_checked_at", sa.DateTime(timezone=False), nullable=True)
    )
    op.add_column("claims", sa.Column("stedi_payer_claim_number", sa.String(), nullable=True))
    op.add_column(
        "patient_insurance_policies",
        sa.Column("group_number", sa.String(), nullable=True),
    )

    op.create_table(
        "claim_status_checks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("checked_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("status_code", sa.String(), nullable=True),
        sa.Column("status_category", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("amount_paid", sa.Numeric(), nullable=True),
        sa.Column("payer_claim_number", sa.String(), nullable=True),
        sa.Column("stedi_trace_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_summary_json", sa.JSON(), nullable=True),
        sa.Column("response_summary_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_claim_status_checks"),
    )
    op.create_index("ix_claim_status_checks_clinic_id", "claim_status_checks", ["clinic_id"])
    op.create_index("ix_claim_status_checks_claim_id", "claim_status_checks", ["claim_id"])
    op.create_index("ix_claim_status_checks_checked_at", "claim_status_checks", ["checked_at"])

    op.execute("ALTER TABLE claim_status_checks ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE claim_status_checks FORCE ROW LEVEL SECURITY;")
    op.execute(
        POLICY_TEMPLATE.format(
            table_name="claim_status_checks",
            policy_name="rls_claim_status_checks_clinic",
        )
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_claim_status_checks_clinic ON claim_status_checks;")
    op.execute("ALTER TABLE claim_status_checks DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_claim_status_checks_checked_at", table_name="claim_status_checks")
    op.drop_index("ix_claim_status_checks_claim_id", table_name="claim_status_checks")
    op.drop_index("ix_claim_status_checks_clinic_id", table_name="claim_status_checks")
    op.drop_table("claim_status_checks")

    op.drop_column("claims", "stedi_payer_claim_number")
    op.drop_column("patient_insurance_policies", "group_number")
    op.drop_column("claims", "stedi_checked_at")
    op.drop_column("claims", "stedi_amount_paid")
    op.drop_column("claims", "stedi_status_message")
    op.drop_column("claims", "stedi_status_category")
    op.drop_column("claims", "stedi_status_code")
    op.drop_column("claims", "submitted_at")
    op.drop_column("claims", "stedi_status")

    op.drop_column("clinics", "billing_provider_organization_name")
    op.drop_column("clinics", "billing_provider_tax_id")
    op.drop_column("clinics", "billing_provider_npi")
    op.drop_column("insurance_companies", "stedi_trading_partner_service_id")
