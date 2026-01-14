"""Claim procedure model."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UpdatedTimestampMixin


class ClaimProcedure(UpdatedTimestampMixin, Base):
    __tablename__ = "claim_procedures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False
    )
    procedure_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedure_codes.id"), nullable=False
    )
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    modifier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    claim = relationship("Claim", back_populates="procedures")
    procedure_code = relationship("ProcedureCode", back_populates="claim_procedures")
