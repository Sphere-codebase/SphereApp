"""Claim-diagnosis association model."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClaimDiagnosis(TimestampMixin, Base):
    __tablename__ = "claim_diagnoses"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        primary_key=True,
        nullable=False,
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnoses.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )

    tenant = relationship("Tenant", backref="claim_diagnoses")
    claim = relationship("Claim", back_populates="diagnosis_links")
    diagnosis = relationship("Diagnosis", backref="claim_links")
