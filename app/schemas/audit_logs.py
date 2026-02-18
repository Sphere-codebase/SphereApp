"""Audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    actor_id: int | None
    actor_role: str | None
    action: str
    entity: str
    entity_id: str | None
    diff_json: dict[str, Any] | None
    request_id: str
    ip: str | None
    user_agent: str | None
    target_clinic_id: int | None
    target_user_id: int | None
    scope: str
    created_at: datetime | None
