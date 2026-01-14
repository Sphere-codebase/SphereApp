"""Admin catalog schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from app.db.models.enums import PolicyLinkStatus


class AgencyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    is_active: bool = True


class AgencyUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1)
    slug: str | None = Field(None, min_length=1)
    is_active: bool | None = None


class AgencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProcedureCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=1)
    title: str | None = None
    category: str | None = None


class ProcedureCodeUpdateRequest(BaseModel):
    code: str | None = Field(None, min_length=1)
    title: str | None = None
    category: str | None = None


class ProcedureCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str | None
    category: str | None
    created_at: datetime
    updated_at: datetime


class PolicyLinkCreateRequest(BaseModel):
    agency_id: uuid.UUID
    procedure_code_id: uuid.UUID
    policy_url: AnyUrl
    effective_from: date | None = None
    effective_to: date | None = None
    status: PolicyLinkStatus = PolicyLinkStatus.ACTIVE
    notes: str | None = None


class PolicyLinkUpdateRequest(BaseModel):
    agency_id: uuid.UUID | None = None
    procedure_code_id: uuid.UUID | None = None
    policy_url: AnyUrl | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: PolicyLinkStatus | None = None
    notes: str | None = None


class PolicyLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    procedure_code_id: uuid.UUID
    policy_url: AnyUrl
    effective_from: date | None
    effective_to: date | None
    status: PolicyLinkStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
