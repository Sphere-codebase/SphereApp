"""Claim MCP code association."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class ClaimMcpCode(Base):
    __tablename__ = "claim_mcp_codes"

    claim_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("claims.id"), primary_key=True
    )
    mcp_code: Mapped[str] = mapped_column(
        String, ForeignKey("mcp_codes.code"), primary_key=True
    )
