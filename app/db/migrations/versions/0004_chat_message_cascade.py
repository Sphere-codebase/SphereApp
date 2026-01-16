"""Add cascade delete for chat messages."""

from __future__ import annotations

from alembic import op

revision = "0004_chat_message_cascade"
down_revision = "0003_add_user_admin_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
    )
