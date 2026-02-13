"""Insurance card metadata model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class InsuranceCard(Base):
    __tablename__ = "insurance_cards"
    __table_args__ = (Index("ix_insurance_cards_policy_id_side", "policy_id", "side"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    policy_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("patient_insurance_policies.id"),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    policy = relationship("PatientInsurancePolicy", back_populates="cards")
