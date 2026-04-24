"""Virtual claim checklist models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat import ChatSession
    from app.db.models.claim import Claim
    from app.db.models.insurance_company import InsuranceCompany
    from app.db.models.patient import Patient
    from app.db.models.policy_link import PolicyLink
    from app.db.models.policy_rule import PolicyRule
    from app.db.models.user import User


class VirtualClaimDraft(TimestampMixin, Base):
    __tablename__ = "virtual_claim_drafts"
    __table_args__ = (
        Index("ix_virtual_claim_drafts_chat_session_id", "chat_session_id", unique=True),
        Index("ix_virtual_claim_drafts_doctor_id", "doctor_id"),
        Index("ix_virtual_claim_drafts_clinic_id", "clinic_id"),
        Index("ix_virtual_claim_drafts_patient_id", "patient_id"),
        Index("ix_virtual_claim_drafts_insurance_company_id", "insurance_company_id"),
        Index("ix_virtual_claim_drafts_status", "status"),
        CheckConstraint(
            "status IN ('open', 'ready', 'materialized', 'archived')",
            name="ck_virtual_claim_drafts_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    chat_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    patient_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )
    insurance_company_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("insurance_companies.id", ondelete="SET NULL"),
        nullable=True,
    )
    procedure_code: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("mcp_codes.code", ondelete="SET NULL"),
        nullable=True,
    )
    selected_policy_link_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("policy_links.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_policy_rule_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("policy_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    materialized_claim_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("claims.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'open'"),
    )
    readiness: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    readiness_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    chat_session: Mapped[ChatSession] = relationship(
        "ChatSession",
        back_populates="virtual_claim_draft",
    )
    doctor: Mapped[User] = relationship("User")
    patient: Mapped[Patient | None] = relationship("Patient")
    insurance_company: Mapped[InsuranceCompany | None] = relationship("InsuranceCompany")
    selected_policy_link: Mapped[PolicyLink | None] = relationship(
        "PolicyLink",
        foreign_keys=[selected_policy_link_id],
    )
    selected_policy_rule: Mapped[PolicyRule | None] = relationship(
        "PolicyRule",
        foreign_keys=[selected_policy_rule_id],
    )
    materialized_claim: Mapped[Claim | None] = relationship(
        "Claim",
        foreign_keys=[materialized_claim_id],
    )
    fields: Mapped[list[VirtualClaimField]] = relationship(
        "VirtualClaimField",
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    questions: Mapped[list[VirtualClaimQuestion]] = relationship(
        "VirtualClaimQuestion",
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class VirtualClaimField(TimestampMixin, Base):
    __tablename__ = "virtual_claim_fields"
    __table_args__ = (
        Index("ix_virtual_claim_fields_draft_id", "draft_id"),
        Index("ix_virtual_claim_fields_clinic_id", "clinic_id"),
        Index("ix_virtual_claim_fields_field_key", "field_key"),
        Index("ix_virtual_claim_fields_draft_id_field_key", "draft_id", "field_key", unique=True),
        CheckConstraint(
            "status IN ('missing', 'present', 'derived', 'needs_review')",
            name="ck_virtual_claim_fields_status",
        ),
        CheckConstraint(
            "source_type IN ('database', 'user', 'llm_extracted', 'derived', 'policy')",
            name="ck_virtual_claim_fields_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    draft_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("virtual_claim_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    value_json: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = (
        mapped_column(JSONB, nullable=True)
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'missing'"))
    source_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'user'"),
    )
    source_ref_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    draft: Mapped[VirtualClaimDraft] = relationship("VirtualClaimDraft", back_populates="fields")


class VirtualClaimQuestion(TimestampMixin, Base):
    __tablename__ = "virtual_claim_questions"
    __table_args__ = (
        Index("ix_virtual_claim_questions_draft_id", "draft_id"),
        Index("ix_virtual_claim_questions_clinic_id", "clinic_id"),
        Index("ix_virtual_claim_questions_question_key", "question_key"),
        CheckConstraint(
            "status IN ('open', 'answered', 'dismissed')",
            name="ck_virtual_claim_questions_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    draft_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("virtual_claim_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    question_key: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'open'"))
    answer_json: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = (
        mapped_column(JSONB, nullable=True)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    draft: Mapped[VirtualClaimDraft] = relationship(
        "VirtualClaimDraft",
        back_populates="questions",
    )
