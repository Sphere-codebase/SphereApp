"""Patient insurance policy model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class PatientInsurancePolicy(TimestampMixin, Base):
    __tablename__ = "patient_insurance_policies"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('primary', 'secondary')",
            name="ck_patient_insurance_policies_priority",
        ),
        Index(
            "ix_patient_insurance_policies_clinic_id_patient_id",
            "clinic_id",
            "patient_id",
        ),
        Index(
            "uq_patient_insurance_policies_patient_id_priority",
            "patient_id",
            "priority",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    clinic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clinics.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("patients.id"), nullable=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    priority: Mapped[str] = mapped_column(String, nullable=False)
    member_id: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_type: Mapped[str | None] = mapped_column(String, nullable=True)
    copay_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    deductible_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    clinic = relationship("Clinic", back_populates="insurance_policies")
    patient = relationship("Patient", back_populates="insurance_policies")
    insurance_company = relationship("InsuranceCompany", back_populates="patient_policies")
    cards = relationship("InsuranceCard", back_populates="policy")
