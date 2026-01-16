"""ML prediction model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class MlPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        Index("ix_ml_predictions_model_version", "model_version"),
        Index("ix_ml_predictions_claim_id_mcp_code", "claim_id", "mcp_code"),
        Index(
            "ix_ml_predictions_insurance_company_id_mcp_code",
            "insurance_company_id",
            "mcp_code",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    claim_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("claims.id"), nullable=False)
    mcp_code: Mapped[str] = mapped_column(String, ForeignKey("mcp_codes.code"), nullable=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    prediction: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    claim = relationship("Claim", backref="ml_predictions")
    insurance_company = relationship("InsuranceCompany", backref="ml_predictions")
