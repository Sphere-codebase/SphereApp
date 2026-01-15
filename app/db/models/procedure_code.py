"""Procedure code (CPT) model."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UpdatedTimestampMixin


class ProcedureCode(UpdatedTimestampMixin, Base):
    __tablename__ = "procedure_codes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_procedure_codes_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    tenant = relationship("Tenant", backref="procedure_codes")
    policy_links = relationship("AgencyProcedurePolicyLink", back_populates="procedure_code")
    claim_procedures = relationship("ClaimProcedure", back_populates="procedure_code")
