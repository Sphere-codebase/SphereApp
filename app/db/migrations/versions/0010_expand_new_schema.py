"""Expand to new schema with parallel tables and mapping helpers."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_expand_new_schema"
down_revision = "0009_agency_slug_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("users", "users_old")
    op.rename_table("patients", "patients_old")
    op.rename_table("claims", "claims_old")
    op.rename_table("chat_sessions", "chat_sessions_old")
    op.rename_table("chat_messages", "chat_messages_old")

    op.execute(
        """
        DO $$
        DECLARE
            r RECORD;
            new_name TEXT;
        BEGIN
            FOR r IN
                SELECT conname, relname
                FROM pg_constraint
                JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
                WHERE relname IN (
                    'users_old',
                    'patients_old',
                    'claims_old',
                    'chat_sessions_old',
                    'chat_messages_old'
                )
            LOOP
                new_name := CASE
                    WHEN length(r.conname) > 55 THEN left(r.conname, 55) || '_old'
                    ELSE r.conname || '_old'
                END;
                EXECUTE format(
                    'ALTER TABLE %I RENAME CONSTRAINT %I TO %I',
                    r.relname,
                    r.conname,
                    new_name
                );
            END LOOP;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            r RECORD;
            new_name TEXT;
        BEGIN
            FOR r IN
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE tablename IN (
                    'users_old',
                    'patients_old',
                    'claims_old',
                    'chat_sessions_old',
                    'chat_messages_old'
                )
            LOOP
                new_name := CASE
                    WHEN length(r.indexname) > 55 THEN left(r.indexname, 55) || '_old'
                    ELSE r.indexname || '_old'
                END;
                EXECUTE format('ALTER INDEX %I RENAME TO %I', r.indexname, new_name);
            END LOOP;
        END
        $$;
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
    )
    op.create_table(
        "insurance_companies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_table(
        "mcp_codes",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("description", sa.String(), nullable=True),
    )
    op.create_table(
        "diagnosis_codes",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("description", sa.String(), nullable=True),
    )
    op.create_table(
        "policy_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.Column("policy_url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
    )
    op.create_index(
        "ix_policy_links_insurance_company_id_mcp_code",
        "policy_links",
        ["insurance_company_id", "mcp_code"],
    )
    op.create_index(
        "uq_policy_links_insurance_company_id_mcp_code_policy_url",
        "policy_links",
        ["insurance_company_id", "mcp_code", "policy_url"],
        unique=True,
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
    )
    op.create_index("ix_patients_doctor_id", "patients", ["doctor_id"])
    op.create_table(
        "claims",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("claim_number", sa.String(), nullable=True),
        sa.Column("claim_status", sa.String(), nullable=True),
        sa.Column("claim_date", sa.Date(), nullable=True),
        sa.Column("billed_amount_total", sa.Numeric(), nullable=True),
        sa.Column("allowed_amount_total", sa.Numeric(), nullable=True),
        sa.Column("coinsurance_amount_total", sa.Numeric(), nullable=True),
        sa.Column("copay_amount_total", sa.Numeric(), nullable=True),
        sa.Column("deductible_amount_total", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
    )
    op.create_index("ix_claims_doctor_id", "claims", ["doctor_id"])
    op.create_index("ix_claims_patient_id", "claims", ["patient_id"])
    op.create_index("ix_claims_insurance_company_id", "claims", ["insurance_company_id"])
    op.create_index("ix_claims_claim_number", "claims", ["claim_number"])
    op.create_table(
        "claim_mcp_codes",
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("claim_id", "mcp_code"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
    )
    op.create_table(
        "claim_diagnosis_codes",
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("diagnosis_code", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("claim_id", "diagnosis_code"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["diagnosis_code"], ["diagnosis_codes.code"]),
    )
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
    )
    op.create_index("ix_chat_sessions_doctor_id", "chat_sessions", ["doctor_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_table(
        "claim_line_coverage",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.Column("policy_link_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
        sa.ForeignKeyConstraint(["policy_link_id"], ["policy_links.id"]),
    )
    op.create_index(
        "uq_claim_line_coverage_claim_id_mcp_code",
        "claim_line_coverage",
        ["claim_id", "mcp_code"],
        unique=True,
    )
    op.create_index("ix_claim_line_coverage_status", "claim_line_coverage", ["status"])
    op.create_index(
        "ix_claim_line_coverage_policy_link_id",
        "claim_line_coverage",
        ["policy_link_id"],
    )
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("policy_link_id", sa.BigInteger(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["policy_link_id"], ["policy_links.id"]),
    )
    op.create_index("ix_policy_rules_policy_link_id", "policy_rules", ["policy_link_id"])
    op.create_index("ix_policy_rules_extracted_at", "policy_rules", ["extracted_at"])
    op.create_table(
        "ml_training_examples",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=True),
        sa.Column("mcp_code", sa.String(), nullable=True),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("label_source", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
    )
    op.create_index("ix_ml_training_examples_label", "ml_training_examples", ["label"])
    op.create_index(
        "ix_ml_training_examples_insurance_company_id",
        "ml_training_examples",
        ["insurance_company_id"],
    )
    op.create_index("ix_ml_training_examples_mcp_code", "ml_training_examples", ["mcp_code"])
    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("prediction", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
    )
    op.create_index("ix_ml_predictions_model_version", "ml_predictions", ["model_version"])
    op.create_index(
        "ix_ml_predictions_claim_id_mcp_code", "ml_predictions", ["claim_id", "mcp_code"]
    )
    op.create_index(
        "ix_ml_predictions_insurance_company_id_mcp_code",
        "ml_predictions",
        ["insurance_company_id", "mcp_code"],
    )
    op.create_table(
        "claim_procedure_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=True),
        sa.Column("pos", sa.String(), nullable=True),
        sa.Column("units", sa.Numeric(), nullable=True),
        sa.Column("modifier", sa.String(), nullable=True),
        sa.Column("billed_amount", sa.Numeric(), nullable=True),
        sa.Column("allowed_amount", sa.Numeric(), nullable=True),
        sa.Column("coinsurance_amount", sa.Numeric(), nullable=True),
        sa.Column("copay_amount", sa.Numeric(), nullable=True),
        sa.Column("deductible_amount", sa.Numeric(), nullable=True),
        sa.Column("paid_amount", sa.Numeric(), nullable=True),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
    )
    op.create_index("ix_claim_procedure_facts_claim_id", "claim_procedure_facts", ["claim_id"])
    op.create_index(
        "ix_claim_procedure_facts_insurance_company_id_mcp_code",
        "claim_procedure_facts",
        ["insurance_company_id", "mcp_code"],
    )
    op.create_index(
        "ix_claim_procedure_facts_service_date",
        "claim_procedure_facts",
        ["service_date"],
    )
    op.create_index("ix_claim_procedure_facts_pos", "claim_procedure_facts", ["pos"])
    op.create_index(
        "ix_claim_proc_facts_code_company_service_date",
        "claim_procedure_facts",
        ["mcp_code", "insurance_company_id", "service_date"],
    )
    op.create_table(
        "claim_procedure_diagnosis",
        sa.Column("claim_procedure_fact_id", sa.BigInteger(), nullable=False),
        sa.Column("diagnosis_code", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("claim_procedure_fact_id", "diagnosis_code"),
        sa.ForeignKeyConstraint(["claim_procedure_fact_id"], ["claim_procedure_facts.id"]),
        sa.ForeignKeyConstraint(["diagnosis_code"], ["diagnosis_codes.code"]),
    )
    op.create_table(
        "mcp_payment_predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=False),
        sa.Column("mcp_code", sa.String(), nullable=False),
        sa.Column("predicted_paid_amount", sa.Numeric(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["insurance_company_id"], ["insurance_companies.id"]),
        sa.ForeignKeyConstraint(["mcp_code"], ["mcp_codes.code"]),
    )
    op.create_index(
        "ix_mcp_payment_predictions_model_version", "mcp_payment_predictions", ["model_version"]
    )
    op.create_index(
        "ix_mcp_payment_predictions_prediction_date",
        "mcp_payment_predictions",
        ["prediction_date"],
    )
    op.create_index(
        "uq_mcp_payment_predictions_company_code_date",
        "mcp_payment_predictions",
        ["insurance_company_id", "mcp_code", "prediction_date"],
        unique=True,
    )

    op.create_table(
        "id_map_users",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_insurance_companies",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_patients",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_claims",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_chat_sessions",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_chat_messages",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )
    op.create_table(
        "id_map_claim_procedures",
        sa.Column("old_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("new_id", sa.BigInteger(), nullable=False, unique=True),
    )


def downgrade() -> None:
    op.drop_table("id_map_claim_procedures")
    op.drop_table("id_map_chat_messages")
    op.drop_table("id_map_chat_sessions")
    op.drop_table("id_map_claims")
    op.drop_table("id_map_patients")
    op.drop_table("id_map_insurance_companies")
    op.drop_table("id_map_users")

    op.drop_table("mcp_payment_predictions")
    op.drop_table("claim_procedure_diagnosis")
    op.drop_table("claim_procedure_facts")
    op.drop_table("ml_predictions")
    op.drop_table("ml_training_examples")
    op.drop_table("policy_rules")
    op.drop_table("claim_line_coverage")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("claim_diagnosis_codes")
    op.drop_table("claim_mcp_codes")
    op.drop_table("claims")
    op.drop_table("patients")
    op.drop_table("policy_links")
    op.drop_table("diagnosis_codes")
    op.drop_table("mcp_codes")
    op.drop_table("insurance_companies")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")

    op.rename_table("chat_messages_old", "chat_messages")
    op.rename_table("chat_sessions_old", "chat_sessions")
    op.rename_table("claims_old", "claims")
    op.rename_table("patients_old", "patients")
    op.rename_table("users_old", "users")
