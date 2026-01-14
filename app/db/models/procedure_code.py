"""Procedure code (CPT) model."""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UpdatedTimestampMixin


class ProcedureCode(UpdatedTimestampMixin, Base):
    __tablename__ = "procedure_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    policy_links = relationship("AgencyProcedurePolicyLink", back_populates="procedure_code")
    claim_procedures = relationship("ClaimProcedure", back_populates="procedure_code")
