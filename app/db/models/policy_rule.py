"""Policy rule model."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        Index("ix_policy_rules_policy_link_id", "policy_link_id"),
        Index("ix_policy_rules_extracted_at", "extracted_at"),
        Index("ix_policy_rules_policy_link_id_extracted_at", "policy_link_id", "extracted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    policy_link_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policy_links.id"), nullable=False
    )
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_review_iso: Mapped[date | None] = mapped_column(Date, nullable=True)
    criteria_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notes_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    policy_link = relationship("PolicyLink", backref="rules")
