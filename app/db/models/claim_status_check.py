"""Claim status check history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class ClaimStatusCheck(Base):
    __tablename__ = "claim_status_checks"
    __table_args__ = (
        Index("ix_claim_status_checks_clinic_id", "clinic_id"),
        Index("ix_claim_status_checks_claim_id", "claim_id"),
        Index("ix_claim_status_checks_checked_at", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )
    claim_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("claims.id"), nullable=False)
    checked_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status_category: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_paid: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    payer_claim_number: Mapped[str | None] = mapped_column(String, nullable=True)
    stedi_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    claim = relationship("Claim", backref="status_checks")
    checked_by = relationship("User", backref="claim_status_checks")
