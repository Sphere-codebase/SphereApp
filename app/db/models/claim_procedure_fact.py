"""Claim procedure fact model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClaimProcedureFact(TimestampMixin, Base):
    __tablename__ = "claim_procedure_facts"
    __table_args__ = (
        Index("ix_claim_procedure_facts_claim_id", "claim_id"),
        Index(
            "ix_claim_procedure_facts_insurance_company_id_mcp_code",
            "insurance_company_id",
            "mcp_code",
        ),
        Index("ix_claim_procedure_facts_service_date", "service_date"),
        Index("ix_claim_procedure_facts_pos", "pos"),
        Index(
            "ix_claim_proc_facts_code_company_service_date",
            "mcp_code",
            "insurance_company_id",
            "service_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    claim_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("claims.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    mcp_code: Mapped[str] = mapped_column(String, ForeignKey("mcp_codes.code"), nullable=False)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pos: Mapped[str | None] = mapped_column(String, nullable=True)
    units: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    modifier: Mapped[str | None] = mapped_column(String, nullable=True)
    billed_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    allowed_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    coinsurance_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    copay_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    deductible_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    paid_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    claim = relationship("Claim", backref="procedure_facts")
    patient = relationship("Patient", backref="procedure_facts")
    insurance_company = relationship("InsuranceCompany", backref="procedure_facts")
