"""Add admin catalogs and patient/visit/claim extensions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_domain_expansion"
down_revision = "0004_chat_message_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    claim_status = postgresql.ENUM(
        "DRAFT", "SUBMITTED", "PAID", "DENIED", name="claim_status", create_type=False
    )
    policy_link_status = postgresql.ENUM(
        "ACTIVE", "INACTIVE", name="policy_link_status", create_type=False
    )
    claim_status.create(op.get_bind(), checkfirst=True)
    policy_link_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "agencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "procedure_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "agency_procedure_policy_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procedure_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_url", sa.String(length=2048), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", policy_link_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"],
            ["agencies.id"],
            name="fk_policy_links_agency_id",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_code_id"],
            ["procedure_codes.id"],
            name="fk_policy_links_procedure_code_id",
        ),
    )
    op.create_index(
        "ix_policy_links_agency_procedure",
        "agency_procedure_policy_links",
        ["agency_id", "procedure_code_id"],
    )
    op.create_index(
        "ix_policy_links_procedure_code_id",
        "agency_procedure_policy_links",
        ["procedure_code_id"],
    )
    op.create_index(
        "uq_policy_links_active",
        "agency_procedure_policy_links",
        ["agency_id", "procedure_code_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column("patients", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("patients", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("sex", sa.String(length=32), nullable=True))
    op.add_column(
        "patients",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_patients_user_id", "patients", ["user_id"])
    op.create_foreign_key(
        "fk_patients_user_id_users",
        "patients",
        "users",
        ["user_id"],
        ["id"],
    )

    op.add_column("claims", sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("claims", sa.Column("claim_number", sa.String(length=100), nullable=True))
    op.add_column("claims", sa.Column("service_from", sa.Date(), nullable=True))
    op.add_column("claims", sa.Column("service_to", sa.Date(), nullable=True))
    op.add_column(
        "claims",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_claims_agency_id_agencies",
        "claims",
        "agencies",
        ["agency_id"],
        ["id"],
    )
    op.create_index("ix_claims_agency_id", "claims", ["agency_id"])
    op.create_index("ix_claims_patient_id", "claims", ["patient_id"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_unique_constraint(
        "uq_claims_agency_id_claim_number",
        "claims",
        ["agency_id", "claim_number"],
    )

    op.execute(
        "UPDATE claims SET status = 'DRAFT' "
        "WHERE status IS NULL OR LOWER(status) IN ('open', 'draft')"
    )
    op.alter_column(
        "claims",
        "status",
        existing_type=sa.String(length=50),
        type_=claim_status,
        postgresql_using="status::text::claim_status",
        existing_nullable=False,
    )

    op.create_table(
        "visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name="fk_visits_patient_id_patients"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_visits_tenant_id_tenants"),
    )
    op.create_index("ix_visits_patient_id", "visits", ["patient_id"])
    op.create_index("ix_visits_visited_at", "visits", ["visited_at"])
    op.create_index("ix_visits_tenant_id", "visits", ["tenant_id"])

    op.create_table(
        "patient_diagnoses",
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagnosis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["diagnosis_id"], ["diagnoses.id"], name="fk_patient_diagnoses_diagnosis_id_diagnoses"
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name="fk_patient_diagnoses_patient_id_patients"
        ),
        sa.PrimaryKeyConstraint("patient_id", "diagnosis_id", name="pk_patient_diagnoses"),
    )

    op.create_table(
        "claim_visits",
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name="fk_claim_visits_claim_id_claims"
        ),
        sa.ForeignKeyConstraint(
            ["visit_id"], ["visits.id"], name="fk_claim_visits_visit_id_visits"
        ),
        sa.PrimaryKeyConstraint("claim_id", "visit_id", name="pk_claim_visits"),
        sa.UniqueConstraint("claim_id", "visit_id", name="uq_claim_visits_claim_id_visit_id"),
    )

    op.create_table(
        "claim_procedures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procedure_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("modifier", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name="fk_claim_procedures_claim_id_claims"
        ),
        sa.ForeignKeyConstraint(
            ["procedure_code_id"],
            ["procedure_codes.id"],
            name="fk_claim_procedures_procedure_code_id_procedure_codes",
        ),
        sa.UniqueConstraint(
            "claim_id",
            "procedure_code_id",
            "modifier",
            name="uq_claim_procedures_claim_id_procedure_code_id_modifier",
        ),
    )
    op.create_index("ix_claim_procedures_claim_id", "claim_procedures", ["claim_id"])
    op.create_index(
        "ix_claim_procedures_procedure_code_id", "claim_procedures", ["procedure_code_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_claim_procedures_procedure_code_id", table_name="claim_procedures")
    op.drop_index("ix_claim_procedures_claim_id", table_name="claim_procedures")
    op.drop_table("claim_procedures")
    op.drop_table("claim_visits")
    op.drop_table("patient_diagnoses")
    op.drop_index("ix_visits_tenant_id", table_name="visits")
    op.drop_index("ix_visits_visited_at", table_name="visits")
    op.drop_index("ix_visits_patient_id", table_name="visits")
    op.drop_table("visits")

    op.alter_column(
        "claims",
        "status",
        existing_type=sa.Enum(name="claim_status"),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.drop_constraint("uq_claims_agency_id_claim_number", "claims", type_="unique")
    op.drop_index("ix_claims_status", table_name="claims")
    op.drop_index("ix_claims_patient_id", table_name="claims")
    op.drop_index("ix_claims_agency_id", table_name="claims")
    op.drop_constraint("fk_claims_agency_id_agencies", "claims", type_="foreignkey")
    op.drop_column("claims", "updated_at")
    op.drop_column("claims", "service_to")
    op.drop_column("claims", "service_from")
    op.drop_column("claims", "claim_number")
    op.drop_column("claims", "agency_id")

    op.drop_constraint("fk_patients_user_id_users", "patients", type_="foreignkey")
    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_column("patients", "updated_at")
    op.drop_column("patients", "sex")
    op.drop_column("patients", "last_name")
    op.drop_column("patients", "first_name")
    op.drop_column("patients", "user_id")

    op.drop_table("diagnoses")
    op.drop_index("uq_policy_links_active", table_name="agency_procedure_policy_links")
    op.drop_index("ix_policy_links_procedure_code_id", table_name="agency_procedure_policy_links")
    op.drop_index("ix_policy_links_agency_procedure", table_name="agency_procedure_policy_links")
    op.drop_table("agency_procedure_policy_links")
    op.drop_table("procedure_codes")
    op.drop_table("agencies")

    op.execute("DROP TYPE IF EXISTS policy_link_status")
    op.execute("DROP TYPE IF EXISTS claim_status")
