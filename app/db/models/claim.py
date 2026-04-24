"""Claim model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.chat import ChatSession
    from app.db.models.claim_pdf import ClaimPDF
    from app.db.models.virtual_claim import VirtualClaimDraft


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        Index("ix_claims_clinic_id", "clinic_id"),
        Index("ix_claims_doctor_id", "doctor_id"),
        Index("ix_claims_patient_id", "patient_id"),
        Index("ix_claims_insurance_company_id", "insurance_company_id"),
        Index("ix_claims_claim_number", "claim_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    claim_number: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_status: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    billed_amount_total: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    allowed_amount_total: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    coinsurance_amount_total: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    copay_amount_total: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    deductible_amount_total: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    doctor = relationship("User", backref="claims")
    patient = relationship("Patient", backref="claims")
    insurance_company = relationship("InsuranceCompany", backref="claims")
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession",
        back_populates="claim",
    )
    claim_pdfs: Mapped[list[ClaimPDF]] = relationship(
        "ClaimPDF",
        back_populates="claim",
    )
    materialized_virtual_claim_drafts: Mapped[list[VirtualClaimDraft]] = relationship(
        "VirtualClaimDraft",
        foreign_keys="VirtualClaimDraft.materialized_claim_id",
    )
