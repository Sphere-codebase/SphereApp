"""Claim procedure diagnosis association."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class ClaimProcedureDiagnosis(Base):
    __tablename__ = "claim_procedure_diagnosis"

    claim_procedure_fact_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("claim_procedure_facts.id"), primary_key=True
    )
    diagnosis_code: Mapped[str] = mapped_column(
        String, ForeignKey("diagnosis_codes.code"), primary_key=True
    )
