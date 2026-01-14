"""Add ML-ready claim and procedure aggregates."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_ml_ready_schema_v1"
down_revision = "0005_domain_expansion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("claims", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("claims", sa.Column("billed_total_cents", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("allowed_total_cents", sa.Integer(), nullable=True))
    op.add_column("claims", sa.Column("paid_total_cents", sa.Integer(), nullable=True))
    op.add_column(
        "claims", sa.Column("patient_responsibility_cents", sa.Integer(), nullable=True)
    )
    op.create_index("ix_claims_tenant_patient", "claims", ["tenant_id", "patient_id"])
    op.create_index("ix_claims_tenant_agency", "claims", ["tenant_id", "agency_id"])
    op.create_index("ix_claims_tenant_status", "claims", ["tenant_id", "status"])
    op.create_check_constraint(
        "ck_claims_billed_total_cents_gte_0",
        "claims",
        "billed_total_cents >= 0 OR billed_total_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claims_allowed_total_cents_gte_0",
        "claims",
        "allowed_total_cents >= 0 OR allowed_total_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claims_paid_total_cents_gte_0",
        "claims",
        "paid_total_cents >= 0 OR paid_total_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claims_patient_resp_cents_gte_0",
        "claims",
        "patient_responsibility_cents >= 0 OR patient_responsibility_cents IS NULL",
    )

    op.add_column(
        "claim_procedures",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "claim_procedures", sa.Column("billed_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("allowed_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("coinsurance_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("copay_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("deductible_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("paid_amount_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "claim_procedures", sa.Column("denial_reason_code", sa.Text(), nullable=True)
    )
    op.add_column("claim_procedures", sa.Column("line_number", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE claim_procedures SET tenant_id = claims.tenant_id "
        "FROM claims WHERE claim_procedures.claim_id = claims.id"
    )
    op.alter_column("claim_procedures", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_claim_procedures_tenant_id",
        "claim_procedures",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_claim_procedures_tenant_claim",
        "claim_procedures",
        ["tenant_id", "claim_id"],
    )
    op.create_index(
        "ix_claim_procedures_tenant_procedure",
        "claim_procedures",
        ["tenant_id", "procedure_code_id"],
    )
    op.create_check_constraint(
        "ck_claim_procedures_units_gte_1",
        "claim_procedures",
        "units >= 1",
    )
    op.create_check_constraint(
        "ck_claim_procedures_billed_amount_cents_gte_0",
        "claim_procedures",
        "billed_amount_cents >= 0 OR billed_amount_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claim_procedures_allowed_amount_cents_gte_0",
        "claim_procedures",
        "allowed_amount_cents >= 0 OR allowed_amount_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claim_procedures_coinsurance_amount_cents_gte_0",
        "claim_procedures",
        "coinsurance_amount_cents >= 0 OR coinsurance_amount_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claim_procedures_copay_amount_cents_gte_0",
        "claim_procedures",
        "copay_amount_cents >= 0 OR copay_amount_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claim_procedures_deductible_amount_cents_gte_0",
        "claim_procedures",
        "deductible_amount_cents >= 0 OR deductible_amount_cents IS NULL",
    )
    op.create_check_constraint(
        "ck_claim_procedures_paid_amount_cents_gte_0",
        "claim_procedures",
        "paid_amount_cents >= 0 OR paid_amount_cents IS NULL",
    )

    op.create_table(
        "claim_diagnoses",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_claim_diagnoses_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_diagnoses_claim_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["diagnosis_id"],
            ["diagnoses.id"],
            name="fk_claim_diagnoses_diagnosis_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "claim_id",
            "diagnosis_id",
            name="pk_claim_diagnoses",
        ),
    )
    op.create_index(
        "ix_claim_diagnoses_tenant_claim",
        "claim_diagnoses",
        ["tenant_id", "claim_id"],
    )
    op.create_index(
        "ix_claim_diagnoses_tenant_diagnosis",
        "claim_diagnoses",
        ["tenant_id", "diagnosis_id"],
    )

    op.create_table(
        "claim_procedure_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_procedure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paid_amount_cents", sa.Integer(), nullable=False),
        sa.Column("adjustment_amount_cents", sa.Integer(), nullable=True),
        sa.Column("adjustment_reason_code", sa.Text(), nullable=True),
        sa.Column("check_number", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_claim_proc_payments_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["claim_procedure_id"],
            ["claim_procedures.id"],
            name="fk_claim_proc_payments_claim_procedure_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_claim_proc_payments_tenant_claim_proc",
        "claim_procedure_payments",
        ["tenant_id", "claim_procedure_id"],
    )
    op.create_index(
        "ix_claim_proc_payments_tenant_paid_at",
        "claim_procedure_payments",
        ["tenant_id", "paid_at"],
    )
    op.create_check_constraint(
        "ck_claim_proc_payments_paid_amount_cents_gte_0",
        "claim_procedure_payments",
        "paid_amount_cents >= 0",
    )
    op.create_check_constraint(
        "ck_claim_proc_payments_adjustment_amount_cents_gte_0",
        "claim_procedure_payments",
        "adjustment_amount_cents >= 0 OR adjustment_amount_cents IS NULL",
    )

    op.create_table(
        "procedure_price_by_agency",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procedure_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("avg_paid_cents", sa.Integer(), nullable=False),
        sa.Column("min_paid_cents", sa.Integer(), nullable=False),
        sa.Column("max_paid_cents", sa.Integer(), nullable=False),
        sa.Column("claims_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_proc_price_agency_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"],
            ["agencies.id"],
            name="fk_proc_price_agency_agency_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_code_id"],
            ["procedure_codes.id"],
            name="fk_proc_price_agency_procedure_code_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "agency_id",
            "procedure_code_id",
            name="uq_proc_price_agency_key",
        ),
    )
    op.create_index(
        "ix_proc_price_agency_tenant_agency",
        "procedure_price_by_agency",
        ["tenant_id", "agency_id"],
    )
    op.create_index(
        "ix_proc_price_agency_tenant_procedure",
        "procedure_price_by_agency",
        ["tenant_id", "procedure_code_id"],
    )
    op.create_check_constraint(
        "ck_proc_price_agency_avg_paid_cents_gte_0",
        "procedure_price_by_agency",
        "avg_paid_cents >= 0",
    )
    op.create_check_constraint(
        "ck_proc_price_agency_min_paid_cents_gte_0",
        "procedure_price_by_agency",
        "min_paid_cents >= 0",
    )
    op.create_check_constraint(
        "ck_proc_price_agency_max_paid_cents_gte_0",
        "procedure_price_by_agency",
        "max_paid_cents >= 0",
    )
    op.create_check_constraint(
        "ck_proc_price_agency_claims_count_gte_0",
        "procedure_price_by_agency",
        "claims_count >= 0",
    )


def downgrade() -> None:
    op.drop_check_constraint(
        "ck_proc_price_agency_claims_count_gte_0", "procedure_price_by_agency"
    )
    op.drop_check_constraint(
        "ck_proc_price_agency_max_paid_cents_gte_0", "procedure_price_by_agency"
    )
    op.drop_check_constraint(
        "ck_proc_price_agency_min_paid_cents_gte_0", "procedure_price_by_agency"
    )
    op.drop_check_constraint(
        "ck_proc_price_agency_avg_paid_cents_gte_0", "procedure_price_by_agency"
    )
    op.drop_index("ix_proc_price_agency_tenant_procedure", table_name="procedure_price_by_agency")
    op.drop_index("ix_proc_price_agency_tenant_agency", table_name="procedure_price_by_agency")
    op.drop_table("procedure_price_by_agency")

    op.drop_check_constraint(
        "ck_claim_proc_payments_adjustment_amount_cents_gte_0",
        "claim_procedure_payments",
    )
    op.drop_check_constraint(
        "ck_claim_proc_payments_paid_amount_cents_gte_0", "claim_procedure_payments"
    )
    op.drop_index(
        "ix_claim_proc_payments_tenant_paid_at", table_name="claim_procedure_payments"
    )
    op.drop_index(
        "ix_claim_proc_payments_tenant_claim_proc", table_name="claim_procedure_payments"
    )
    op.drop_table("claim_procedure_payments")

    op.drop_index("ix_claim_diagnoses_tenant_diagnosis", table_name="claim_diagnoses")
    op.drop_index("ix_claim_diagnoses_tenant_claim", table_name="claim_diagnoses")
    op.drop_table("claim_diagnoses")

    op.drop_check_constraint("ck_claim_procedures_paid_amount_cents_gte_0", "claim_procedures")
    op.drop_check_constraint(
        "ck_claim_procedures_deductible_amount_cents_gte_0", "claim_procedures"
    )
    op.drop_check_constraint(
        "ck_claim_procedures_copay_amount_cents_gte_0", "claim_procedures"
    )
    op.drop_check_constraint(
        "ck_claim_procedures_coinsurance_amount_cents_gte_0", "claim_procedures"
    )
    op.drop_check_constraint(
        "ck_claim_procedures_allowed_amount_cents_gte_0", "claim_procedures"
    )
    op.drop_check_constraint(
        "ck_claim_procedures_billed_amount_cents_gte_0", "claim_procedures"
    )
    op.drop_check_constraint("ck_claim_procedures_units_gte_1", "claim_procedures")
    op.drop_index("ix_claim_procedures_tenant_procedure", table_name="claim_procedures")
    op.drop_index("ix_claim_procedures_tenant_claim", table_name="claim_procedures")
    op.drop_constraint("fk_claim_procedures_tenant_id", "claim_procedures", type_="foreignkey")
    op.drop_column("claim_procedures", "line_number")
    op.drop_column("claim_procedures", "denial_reason_code")
    op.drop_column("claim_procedures", "paid_amount_cents")
    op.drop_column("claim_procedures", "deductible_amount_cents")
    op.drop_column("claim_procedures", "copay_amount_cents")
    op.drop_column("claim_procedures", "coinsurance_amount_cents")
    op.drop_column("claim_procedures", "allowed_amount_cents")
    op.drop_column("claim_procedures", "billed_amount_cents")
    op.drop_column("claim_procedures", "tenant_id")

    op.drop_check_constraint("ck_claims_patient_resp_cents_gte_0", "claims")
    op.drop_check_constraint("ck_claims_paid_total_cents_gte_0", "claims")
    op.drop_check_constraint("ck_claims_allowed_total_cents_gte_0", "claims")
    op.drop_check_constraint("ck_claims_billed_total_cents_gte_0", "claims")
    op.drop_index("ix_claims_tenant_status", table_name="claims")
    op.drop_index("ix_claims_tenant_agency", table_name="claims")
    op.drop_index("ix_claims_tenant_patient", table_name="claims")
    op.drop_column("claims", "patient_responsibility_cents")
    op.drop_column("claims", "paid_total_cents")
    op.drop_column("claims", "allowed_total_cents")
    op.drop_column("claims", "billed_total_cents")
    op.drop_column("claims", "finalized_at")
    op.drop_column("claims", "received_at")
