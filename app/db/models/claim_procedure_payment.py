"""Claim procedure payment history model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClaimProcedurePayment(TimestampMixin, Base):
    __tablename__ = "claim_procedure_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    claim_procedure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_procedures.id", ondelete="CASCADE"), nullable=False
    )
    paid_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant = relationship("Tenant", backref="claim_procedure_payments")
    claim_procedure = relationship("ClaimProcedure", back_populates="payments")
