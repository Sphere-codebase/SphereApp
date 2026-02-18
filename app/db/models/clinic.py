"""Clinic model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class Clinic(TimestampMixin, Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("addresses.id"), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    address = relationship("Address", back_populates="clinics")
    users = relationship("User", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")
    insurance_policies = relationship("PatientInsurancePolicy", back_populates="clinic")
