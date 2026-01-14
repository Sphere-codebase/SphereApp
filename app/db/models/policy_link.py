"""Agency procedure policy links."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, UpdatedTimestampMixin
from app.db.models.enums import PolicyLinkStatus


class AgencyProcedurePolicyLink(UpdatedTimestampMixin, Base):
    __tablename__ = "agency_procedure_policy_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False
    )
    procedure_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedure_codes.id"), nullable=False
    )
    policy_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PolicyLinkStatus] = mapped_column(
        Enum(PolicyLinkStatus, name="policy_link_status"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    agency = relationship("Agency", back_populates="policy_links")
    procedure_code = relationship("ProcedureCode", back_populates="policy_links")
