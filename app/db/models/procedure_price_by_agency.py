"""Aggregated procedure pricing stats by agency."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.models.base import Base


class ProcedurePriceByAgency(Base):
    __tablename__ = "procedure_price_by_agency"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    procedure_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedure_codes.id", ondelete="CASCADE"), nullable=False
    )
    avg_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    min_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    max_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    claims_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant = relationship("Tenant", backref="procedure_price_stats")
    agency = relationship("Agency", backref="procedure_price_stats")
    procedure_code = relationship("ProcedureCode", backref="procedure_price_stats")
