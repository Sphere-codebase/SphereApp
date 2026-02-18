"""Claim PDF metadata model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClaimPDF(TimestampMixin, Base):
    __tablename__ = "claim_pdfs"
    __table_args__ = (
        Index("ix_claim_pdfs_claim_id", "claim_id"),
        Index("ix_claim_pdfs_clinic_id", "clinic_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
    )
    claim_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("claims.id"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=True,
    )

    claim = relationship("Claim", back_populates="claim_pdfs")
