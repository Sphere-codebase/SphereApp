"""Claim-diagnosis code association."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class ClaimDiagnosisCode(Base):
    __tablename__ = "claim_diagnosis_codes"

    claim_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("claims.id"), primary_key=True
    )
    diagnosis_code: Mapped[str] = mapped_column(
        String, ForeignKey("diagnosis_codes.code"), primary_key=True
    )
