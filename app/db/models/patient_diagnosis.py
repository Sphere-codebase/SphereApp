"""Patient-diagnosis association model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class PatientDiagnosis(TimestampMixin, Base):
    __tablename__ = "patient_diagnoses"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id"),
        primary_key=True,
        nullable=False,
    )
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnoses.id"),
        primary_key=True,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    patient = relationship("Patient", back_populates="diagnoses")
    diagnosis = relationship("Diagnosis", back_populates="patient_links")
