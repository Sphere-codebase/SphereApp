"""ML training example model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class MlTrainingExample(Base):
    __tablename__ = "ml_training_examples"
    __table_args__ = (
        Index("ix_ml_training_examples_label", "label"),
        Index("ix_ml_training_examples_insurance_company_id", "insurance_company_id"),
        Index("ix_ml_training_examples_mcp_code", "mcp_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    claim_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("claims.id"), nullable=True)
    mcp_code: Mapped[str | None] = mapped_column(
        String, ForeignKey("mcp_codes.code"), nullable=True
    )
    insurance_company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=True
    )
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    label_source: Mapped[str | None] = mapped_column(String, nullable=True)

    claim = relationship("Claim", backref="ml_training_examples")
    insurance_company = relationship("InsuranceCompany", backref="ml_training_examples")
