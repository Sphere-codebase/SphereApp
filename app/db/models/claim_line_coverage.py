"""Claim line coverage model."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClaimLineCoverage(TimestampMixin, Base):
    __tablename__ = "claim_line_coverage"
    __table_args__ = (
        Index("uq_claim_line_coverage_claim_id_mcp_code", "claim_id", "mcp_code", unique=True),
        Index("ix_claim_line_coverage_status", "status"),
        Index("ix_claim_line_coverage_policy_link_id", "policy_link_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    claim_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("claims.id"), nullable=False)
    mcp_code: Mapped[str] = mapped_column(String, ForeignKey("mcp_codes.code"), nullable=False)
    policy_link_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("policy_links.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    claim = relationship("Claim", backref="line_coverages")
    policy_link = relationship("PolicyLink", backref="line_coverages")
