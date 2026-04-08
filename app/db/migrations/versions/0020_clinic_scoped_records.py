"""Add clinic scoping to claims and chat records.

Revision ID: 0020_clinic_scoped_records
Revises: 0019_patient_cards
Create Date: 2026-02-17
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0020_clinic_scoped_records"
down_revision = "0019_patient_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("clinic_id", sa.BigInteger(), nullable=True))
    op.add_column("claim_procedure_facts", sa.Column("clinic_id", sa.BigInteger(), nullable=True))
    op.add_column("claim_line_coverage", sa.Column("clinic_id", sa.BigInteger(), nullable=True))
    op.add_column("chat_sessions", sa.Column("clinic_id", sa.BigInteger(), nullable=True))
    op.add_column("chat_messages", sa.Column("clinic_id", sa.BigInteger(), nullable=True))

    op.create_index("ix_users_clinic_id", "users", ["clinic_id"])
    op.create_index("ix_patients_clinic_id", "patients", ["clinic_id"])
    op.create_index("ix_claims_clinic_id", "claims", ["clinic_id"])
    op.create_index(
        "ix_claim_procedure_facts_clinic_id",
        "claim_procedure_facts",
        ["clinic_id"],
    )
    op.create_index(
        "ix_claim_line_coverage_clinic_id",
        "claim_line_coverage",
        ["clinic_id"],
    )
    op.create_index("ix_chat_sessions_clinic_id", "chat_sessions", ["clinic_id"])
    op.create_index("ix_chat_messages_clinic_id", "chat_messages", ["clinic_id"])

    bind = op.get_bind()
    default_clinic_id = 1
    now = datetime.utcnow()
    existing = bind.execute(
        sa.text("SELECT id FROM clinics WHERE id = :id"),
        {"id": default_clinic_id},
    ).fetchone()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO clinics (id, name, created_at, updated_at) "
                "VALUES (:id, :name, :created_at, :updated_at)"
            ),
            {
                "id": default_clinic_id,
                "name": "Default Clinic",
                "created_at": now,
                "updated_at": now,
            },
        )

    bind.execute(
        sa.text(
            "UPDATE claims "
            "SET clinic_id = users.clinic_id "
            "FROM users "
            "WHERE claims.doctor_id = users.id AND claims.clinic_id IS NULL"
        )
    )
    bind.execute(
        sa.text("UPDATE claims SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    bind.execute(
        sa.text(
            "UPDATE claim_procedure_facts "
            "SET clinic_id = claims.clinic_id "
            "FROM claims "
            "WHERE claim_procedure_facts.claim_id = claims.id "
            "AND claim_procedure_facts.clinic_id IS NULL"
        )
    )
    bind.execute(
        sa.text("UPDATE claim_procedure_facts SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    bind.execute(
        sa.text(
            "UPDATE claim_line_coverage "
            "SET clinic_id = claims.clinic_id "
            "FROM claims "
            "WHERE claim_line_coverage.claim_id = claims.id "
            "AND claim_line_coverage.clinic_id IS NULL"
        )
    )
    bind.execute(
        sa.text("UPDATE claim_line_coverage SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    bind.execute(
        sa.text(
            "UPDATE chat_sessions "
            "SET clinic_id = users.clinic_id "
            "FROM users "
            "WHERE chat_sessions.doctor_id = users.id AND chat_sessions.clinic_id IS NULL"
        )
    )
    bind.execute(
        sa.text("UPDATE chat_sessions SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    bind.execute(
        sa.text(
            "UPDATE chat_messages "
            "SET clinic_id = chat_sessions.clinic_id "
            "FROM chat_sessions "
            "WHERE chat_messages.session_id = chat_sessions.id "
            "AND chat_messages.clinic_id IS NULL"
        )
    )
    bind.execute(
        sa.text("UPDATE chat_messages SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
        {"clinic_id": default_clinic_id},
    )

    op.create_foreign_key(
        "fk_claims_clinic_id_clinics",
        "claims",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_claim_proc_facts_clinic_id_clinics",
        "claim_procedure_facts",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_claim_line_coverage_clinic_id_clinics",
        "claim_line_coverage",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_chat_sessions_clinic_id_clinics",
        "chat_sessions",
        "clinics",
        ["clinic_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_chat_messages_clinic_id_clinics",
        "chat_messages",
        "clinics",
        ["clinic_id"],
        ["id"],
    )

    op.alter_column(
        "claims",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )
    op.alter_column(
        "claim_procedure_facts",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )
    op.alter_column(
        "claim_line_coverage",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )
    op.alter_column(
        "chat_sessions",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )
    op.alter_column(
        "chat_messages",
        "clinic_id",
        nullable=False,
        server_default=sa.text(str(default_clinic_id)),
    )


def downgrade() -> None:
    op.alter_column("chat_messages", "clinic_id", server_default=None, nullable=True)
    op.alter_column("chat_sessions", "clinic_id", server_default=None, nullable=True)
    op.alter_column("claim_line_coverage", "clinic_id", server_default=None, nullable=True)
    op.alter_column("claim_procedure_facts", "clinic_id", server_default=None, nullable=True)
    op.alter_column("claims", "clinic_id", server_default=None, nullable=True)

    op.drop_constraint("fk_chat_messages_clinic_id_clinics", "chat_messages", type_="foreignkey")
    op.drop_constraint("fk_chat_sessions_clinic_id_clinics", "chat_sessions", type_="foreignkey")
    op.drop_constraint(
        "fk_claim_line_coverage_clinic_id_clinics",
        "claim_line_coverage",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_claim_proc_facts_clinic_id_clinics",
        "claim_procedure_facts",
        type_="foreignkey",
    )
    op.drop_constraint("fk_claims_clinic_id_clinics", "claims", type_="foreignkey")

    op.drop_index("ix_chat_messages_clinic_id", table_name="chat_messages")
    op.drop_index("ix_chat_sessions_clinic_id", table_name="chat_sessions")
    op.drop_index("ix_claim_line_coverage_clinic_id", table_name="claim_line_coverage")
    op.drop_index(
        "ix_claim_procedure_facts_clinic_id",
        table_name="claim_procedure_facts",
    )
    op.drop_index("ix_claims_clinic_id", table_name="claims")
    op.drop_index("ix_patients_clinic_id", table_name="patients")
    op.drop_index("ix_users_clinic_id", table_name="users")

    op.drop_column("chat_messages", "clinic_id")
    op.drop_column("chat_sessions", "clinic_id")
    op.drop_column("claim_line_coverage", "clinic_id")
    op.drop_column("claim_procedure_facts", "clinic_id")
    op.drop_column("claims", "clinic_id")
