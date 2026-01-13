"""Initial schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_users_tenant_id_tenants"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_patients_tenant_id_tenants"
        ),
    )
    op.create_index("ix_patients_tenant_id", "patients", ["tenant_id"])
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name="fk_claims_patient_id_patients"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_claims_tenant_id_tenants"),
    )
    op.create_index("ix_claims_tenant_id", "claims", ["tenant_id"])
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], name="fk_payments_claim_id_claims"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_payments_tenant_id_tenants"
        ),
    )
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name="fk_chat_sessions_claim_id_claims"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_chat_sessions_tenant_id_tenants"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_sessions_user_id_users"),
    )
    op.create_index("ix_chat_sessions_tenant_id", "chat_sessions", ["tenant_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("tool_args", postgresql.JSONB(), nullable=True),
        sa.Column("tool_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], name="fk_chat_messages_session_id_chat_sessions"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_chat_messages_tenant_id_tenants"
        ),
    )
    op.create_index("ix_chat_messages_tenant_id", "chat_messages", ["tenant_id"])
    op.create_table(
        "claim_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.id"], name="fk_claim_events_claim_id_claims"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_claim_events_tenant_id_tenants"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_claim_events_user_id_users"),
    )
    op.create_index("ix_claim_events_tenant_id", "claim_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_claim_events_tenant_id", table_name="claim_events")
    op.drop_table("claim_events")
    op.drop_index("ix_chat_messages_tenant_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_tenant_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_payments_tenant_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_claims_tenant_id", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_patients_tenant_id", table_name="patients")
    op.drop_table("patients")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
