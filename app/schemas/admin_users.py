"""Admin user management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=1)
    roles: list[str] | None = None
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    role: str
    roles: list[str]
    created_at: datetime | None


class AdminUserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=1)
