"""Policy rule model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        Index("ix_policy_rules_policy_link_id", "policy_link_id"),
        Index("ix_policy_rules_extracted_at", "extracted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    policy_link_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policy_links.id"), nullable=False
    )
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)

    policy_link = relationship("PolicyLink", backref="rules")
