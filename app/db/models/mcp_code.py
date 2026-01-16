"""MCP code model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class McpCode(Base):
    __tablename__ = "mcp_codes"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    policy_links = relationship("PolicyLink", back_populates="mcp_code_ref")
