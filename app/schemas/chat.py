"""Chat request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: int | None = None
    metadata: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    session_id: int
    assistant_message: str
    ui_actions: list[dict[str, Any]] = Field(default_factory=list)
    debug: dict[str, Any] | None = None
    action_required: bool = False
    proposed_changes: dict[str, Any] | None = None
