"""Unified audit log model."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_clinic_id", "clinic_id"),
        Index("ix_audit_logs_clinic_id_created_at", "clinic_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_entity", "entity"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_request_id", "request_id"),
        Index("ix_audit_logs_target_clinic_id", "target_clinic_id"),
        Index("ix_audit_logs_target_user_id", "target_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    clinic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clinics.id"), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    diff_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_clinic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clinics.id"), nullable=True
    )
    target_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String, nullable=False)
