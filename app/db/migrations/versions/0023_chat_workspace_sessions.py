"""Add chat workspace session fields and claim PDFs.

Revision ID: 0023_chat_workspace_sessions
Revises: 0022_audit_logs
Create Date: 2026-02-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0023_chat_workspace_sessions"
down_revision = "0022_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("claim_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("patient_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("closed_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("closed_reason", sa.String(), nullable=True),
    )

    op.execute(sa.text("UPDATE chat_sessions SET status = 'open' WHERE status IS NULL"))

    op.create_index("ix_chat_sessions_claim_id", "chat_sessions", ["claim_id"])
    op.create_index("ix_chat_sessions_patient_id", "chat_sessions", ["patient_id"])
    op.create_index("ix_chat_sessions_status", "chat_sessions", ["status"])

    op.create_foreign_key(
        "fk_chat_sessions_claim_id_claims",
        "chat_sessions",
        "claims",
        ["claim_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_chat_sessions_patient_id_patients",
        "chat_sessions",
        "patients",
        ["patient_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_chat_sessions_status",
        "chat_sessions",
        "status IN ('open', 'closed')",
    )

    op.create_table(
        "claim_pdfs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("claim_id", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_claim_pdfs_claim_id", "claim_pdfs", ["claim_id"])
    op.create_index("ix_claim_pdfs_clinic_id", "claim_pdfs", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_claim_pdfs_clinic_id", table_name="claim_pdfs")
    op.drop_index("ix_claim_pdfs_claim_id", table_name="claim_pdfs")
    op.drop_table("claim_pdfs")

    op.drop_constraint("ck_chat_sessions_status", "chat_sessions", type_="check")
    op.drop_constraint(
        "fk_chat_sessions_patient_id_patients",
        "chat_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_chat_sessions_claim_id_claims",
        "chat_sessions",
        type_="foreignkey",
    )
    op.drop_index("ix_chat_sessions_status", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_patient_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_claim_id", table_name="chat_sessions")

    op.drop_column("chat_sessions", "closed_reason")
    op.drop_column("chat_sessions", "closed_at")
    op.drop_column("chat_sessions", "status")
    op.drop_column("chat_sessions", "patient_id")
    op.drop_column("chat_sessions", "claim_id")
