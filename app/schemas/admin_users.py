"""Admin user management schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=1)
    is_admin: bool = False
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    tenant_id: uuid.UUID
    is_active: bool
    is_admin: bool
    created_at: datetime


class AdminUserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=1)
