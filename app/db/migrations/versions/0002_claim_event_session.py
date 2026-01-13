"""Add chat_session_id to claim_events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_claim_event_session"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claim_events",
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_claim_events_chat_session_id_chat_sessions",
        "claim_events",
        "chat_sessions",
        ["chat_session_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_claim_events_chat_session_id_chat_sessions",
        "claim_events",
        type_="foreignkey",
    )
    op.drop_column("claim_events", "chat_session_id")
