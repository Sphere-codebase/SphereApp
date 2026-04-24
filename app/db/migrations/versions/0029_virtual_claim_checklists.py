"""Virtual claim checklists.

Revision ID: 0029_virtual_claim_checklists
Revises: 0028_perf_indexes
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0029_virtual_claim_checklists"
down_revision = "0028_perf_indexes"
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
    op.create_table(
        "virtual_claim_drafts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("chat_session_id", sa.BigInteger(), nullable=False),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("patient_id", sa.BigInteger(), nullable=True),
        sa.Column("insurance_company_id", sa.BigInteger(), nullable=True),
        sa.Column("procedure_code", sa.String(), nullable=True),
        sa.Column("selected_policy_link_id", sa.BigInteger(), nullable=True),
        sa.Column("selected_policy_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("materialized_claim_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("readiness", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("readiness_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'ready', 'materialized', 'archived')",
            name="ck_virtual_claim_drafts_status",
        ),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["insurance_company_id"], ["insurance_companies.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["procedure_code"], ["mcp_codes.code"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["selected_policy_link_id"], ["policy_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["selected_policy_rule_id"], ["policy_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["materialized_claim_id"], ["claims.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_virtual_claim_drafts"),
    )
    op.create_index(
        "ix_virtual_claim_drafts_chat_session_id",
        "virtual_claim_drafts",
        ["chat_session_id"],
        unique=True,
    )
    op.create_index("ix_virtual_claim_drafts_doctor_id", "virtual_claim_drafts", ["doctor_id"])
    op.create_index("ix_virtual_claim_drafts_clinic_id", "virtual_claim_drafts", ["clinic_id"])
    op.create_index("ix_virtual_claim_drafts_patient_id", "virtual_claim_drafts", ["patient_id"])
    op.create_index(
        "ix_virtual_claim_drafts_insurance_company_id",
        "virtual_claim_drafts",
        ["insurance_company_id"],
    )
    op.create_index("ix_virtual_claim_drafts_status", "virtual_claim_drafts", ["status"])

    op.create_table(
        "virtual_claim_fields",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("draft_id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'missing'")),
        sa.Column("source_type", sa.String(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("source_ref_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint(
            "status IN ('missing', 'present', 'derived', 'needs_review')",
            name="ck_virtual_claim_fields_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('database', 'user', 'llm_extracted', 'derived', 'policy')",
            name="ck_virtual_claim_fields_source_type",
        ),
        sa.ForeignKeyConstraint(["draft_id"], ["virtual_claim_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_virtual_claim_fields"),
    )
    op.create_index("ix_virtual_claim_fields_draft_id", "virtual_claim_fields", ["draft_id"])
    op.create_index("ix_virtual_claim_fields_clinic_id", "virtual_claim_fields", ["clinic_id"])
    op.create_index("ix_virtual_claim_fields_field_key", "virtual_claim_fields", ["field_key"])
    op.create_index(
        "ix_virtual_claim_fields_draft_id_field_key",
        "virtual_claim_fields",
        ["draft_id", "field_key"],
        unique=True,
    )

    op.create_table(
        "virtual_claim_questions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("draft_id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("question_key", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("answer_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'answered', 'dismissed')",
            name="ck_virtual_claim_questions_status",
        ),
        sa.ForeignKeyConstraint(["draft_id"], ["virtual_claim_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_virtual_claim_questions"),
    )
    op.create_index("ix_virtual_claim_questions_draft_id", "virtual_claim_questions", ["draft_id"])
    op.create_index(
        "ix_virtual_claim_questions_clinic_id",
        "virtual_claim_questions",
        ["clinic_id"],
    )
    op.create_index(
        "ix_virtual_claim_questions_question_key",
        "virtual_claim_questions",
        ["question_key"],
    )

    for table_name in (
        "virtual_claim_drafts",
        "virtual_claim_fields",
        "virtual_claim_questions",
    ):
        policy_name = f"rls_{table_name}_clinic"
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
        op.execute(POLICY_TEMPLATE.format(table_name=table_name, policy_name=policy_name))


def downgrade() -> None:
    for table_name in (
        "virtual_claim_questions",
        "virtual_claim_fields",
        "virtual_claim_drafts",
    ):
        policy_name = f"rls_{table_name}_clinic"
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name};")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_virtual_claim_questions_question_key", table_name="virtual_claim_questions")
    op.drop_index("ix_virtual_claim_questions_clinic_id", table_name="virtual_claim_questions")
    op.drop_index("ix_virtual_claim_questions_draft_id", table_name="virtual_claim_questions")
    op.drop_table("virtual_claim_questions")

    op.drop_index("ix_virtual_claim_fields_draft_id_field_key", table_name="virtual_claim_fields")
    op.drop_index("ix_virtual_claim_fields_field_key", table_name="virtual_claim_fields")
    op.drop_index("ix_virtual_claim_fields_clinic_id", table_name="virtual_claim_fields")
    op.drop_index("ix_virtual_claim_fields_draft_id", table_name="virtual_claim_fields")
    op.drop_table("virtual_claim_fields")

    op.drop_index("ix_virtual_claim_drafts_status", table_name="virtual_claim_drafts")
    op.drop_index(
        "ix_virtual_claim_drafts_insurance_company_id",
        table_name="virtual_claim_drafts",
    )
    op.drop_index("ix_virtual_claim_drafts_patient_id", table_name="virtual_claim_drafts")
    op.drop_index("ix_virtual_claim_drafts_clinic_id", table_name="virtual_claim_drafts")
    op.drop_index("ix_virtual_claim_drafts_doctor_id", table_name="virtual_claim_drafts")
    op.drop_index("ix_virtual_claim_drafts_chat_session_id", table_name="virtual_claim_drafts")
    op.drop_table("virtual_claim_drafts")
