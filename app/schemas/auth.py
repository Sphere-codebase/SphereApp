"""Auth request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=1)
    role: str | None = None
    tenant_name: str | None = None


class DevTokenRequest(BaseModel):
    user_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCreateUserResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    tenant_id: uuid.UUID
    is_active: bool
    is_admin: bool
