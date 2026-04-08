"""Chat session API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatSessionCreateRequest(BaseModel):
    title: str | None = None
    claim_id: int | None = None


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = None
    claim_id: int | None = None


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    created_at: datetime | None
    claim_id: int | None = None
    patient_id: int | None = None
    title: str | None = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime | None
