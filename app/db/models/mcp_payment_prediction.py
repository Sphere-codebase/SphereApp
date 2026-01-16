"""MCP payment prediction model."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class McpPaymentPrediction(Base):
    __tablename__ = "mcp_payment_predictions"
    __table_args__ = (
        Index("ix_mcp_payment_predictions_model_version", "model_version"),
        Index("ix_mcp_payment_predictions_prediction_date", "prediction_date"),
        Index(
            "uq_mcp_payment_predictions_company_code_date",
            "insurance_company_id",
            "mcp_code",
            "prediction_date",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    mcp_code: Mapped[str] = mapped_column(String, ForeignKey("mcp_codes.code"), nullable=False)
    predicted_paid_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    insurance_company = relationship("InsuranceCompany", backref="mcp_payment_predictions")
