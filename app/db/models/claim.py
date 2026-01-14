"""Claim model."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UpdatedTimestampMixin
from app.db.models.enums import ClaimStatus


class Claim(UpdatedTimestampMixin, Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    claim_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status"), nullable=False, default=ClaimStatus.DRAFT
    )
    service_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billed_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_responsibility_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    tenant = relationship("Tenant", backref="claims")
    patient = relationship("Patient", backref="claims")
    agency = relationship("Agency", back_populates="claims")
    visits = relationship("Visit", secondary="claim_visits", back_populates="claims")
    procedures = relationship(
        "ClaimProcedure",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    diagnosis_links = relationship(
        "ClaimDiagnosis",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    diagnoses = relationship(
        "Diagnosis",
        secondary="claim_diagnoses",
        viewonly=True,
    )
