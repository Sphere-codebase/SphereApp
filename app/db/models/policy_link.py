"""Policy link model."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class PolicyLink(TimestampMixin, Base):
    __tablename__ = "policy_links"
    __table_args__ = (
        Index("ix_policy_links_insurance_company_id_mcp_code", "insurance_company_id", "mcp_code"),
        Index(
            "uq_policy_links_insurance_company_id_mcp_code_policy_url",
            "insurance_company_id",
            "mcp_code",
            "policy_url",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    insurance_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("insurance_companies.id"), nullable=False
    )
    mcp_code: Mapped[str] = mapped_column(String, ForeignKey("mcp_codes.code"), nullable=False)
    policy_url: Mapped[str] = mapped_column(String, nullable=False)

    insurance_company = relationship("InsuranceCompany", back_populates="policy_links")
    mcp_code_ref = relationship("McpCode", back_populates="policy_links")
