"""Insurance company model."""

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class InsuranceCompany(TimestampMixin, Base):
    __tablename__ = "insurance_companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    stedi_trading_partner_service_id: Mapped[str | None] = mapped_column(String, nullable=True)

    policy_links = relationship("PolicyLink", back_populates="insurance_company")
    patient_policies = relationship("PatientInsurancePolicy", back_populates="insurance_company")
