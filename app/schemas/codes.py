"""Code lookup schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class McpCodeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None


class DiagnosisCodeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None
