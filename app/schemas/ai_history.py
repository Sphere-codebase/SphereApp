"""AI history schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AIHistoryItem(BaseModel):
    id: int
    created_at: datetime | None
    actor_id: int | None
    actor_name: str | None
    action: str
    entity: str
    entity_id: str | None
    diff_json: dict[str, Any] | None
    request_id: str | None


class AIHistoryResponse(BaseModel):
    items: list[AIHistoryItem]
    limit: int
    offset: int
    total: int
