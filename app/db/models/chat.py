"""Chat session and message models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import Session as OrmSession

from app.db.models.base import Base, TimestampMixin
from app.db.models.claim import Claim
from app.db.models.patient import Patient


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_doctor_id", "doctor_id"),
        Index("ix_chat_sessions_clinic_id", "clinic_id"),
        Index("ix_chat_sessions_claim_id", "claim_id"),
        Index("ix_chat_sessions_patient_id", "patient_id"),
        Index("ix_chat_sessions_status", "status"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_chat_sessions_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("claims.id"),
        nullable=True,
    )
    patient_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("patients.id"),
        nullable=True,
    )
    # Chat Workspace lifecycle:
    # - "open" sessions are interactive for claim building.
    # - "closed" sessions are read-only after claim finalization.
    # `closed_at`/`closed_reason` drive the UX for why the chat is closed.
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'open'"),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    doctor = relationship("User", backref="chat_sessions")
    claim = relationship("Claim", back_populates="chat_sessions")
    patient = relationship("Patient", back_populates="chat_sessions")
    virtual_claim_draft = relationship(
        "VirtualClaimDraft",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
        Index("ix_chat_messages_clinic_id", "clinic_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session = relationship("ChatSession", back_populates="messages")


def _resolve_related_clinic_id(
    session: OrmSession,
    related_cls: type,
    related_id: int,
    related_obj: object | None,
) -> int:
    if related_obj is not None and getattr(related_obj, "id", None) == related_id:
        return related_obj.clinic_id
    related = session.get(related_cls, related_id)
    if related is None:
        raise ValueError(f"{related_cls.__name__} not found for chat session tenant check")
    return related.clinic_id


# Tenant integrity for claim_id/patient_id is enforced in the ORM before flush.
@event.listens_for(OrmSession, "before_flush")
def _chat_session_tenant_guard(
    session: OrmSession,
    flush_context: object,
    instances: object,
) -> None:
    for obj in set(session.new).union(session.dirty):
        if not isinstance(obj, ChatSession):
            continue
        if obj.claim_id is not None:
            claim_clinic_id = _resolve_related_clinic_id(
                session,
                Claim,
                obj.claim_id,
                obj.claim,
            )
            if claim_clinic_id != obj.clinic_id:
                raise ValueError("ChatSession claim clinic mismatch")
        if obj.patient_id is not None:
            patient_clinic_id = _resolve_related_clinic_id(
                session,
                Patient,
                obj.patient_id,
                obj.patient,
            )
            if patient_clinic_id != obj.clinic_id:
                raise ValueError("ChatSession patient clinic mismatch")
