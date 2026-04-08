"""Chat request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

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


class ChatConfirmRequest(BaseModel):
    session_id: int
    proposal_id: str | None = None
    decision: Literal["confirm", "reject"]
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None


class ChatConfirmResponse(BaseModel):
    status: Literal["confirmed", "rejected"]
    result: dict[str, Any] | None = None
