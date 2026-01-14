"""Claim schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import ClaimStatus


class ClaimCreateRequest(BaseModel):
    agency_id: uuid.UUID
    patient_id: uuid.UUID
    claim_number: str | None = None
    status: ClaimStatus = ClaimStatus.DRAFT
    service_from: date | None = None
    service_to: date | None = None


class ClaimUpdateRequest(BaseModel):
    agency_id: uuid.UUID | None = None
    claim_number: str | None = None
    status: ClaimStatus | None = None
    service_from: date | None = None
    service_to: date | None = None


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    patient_id: uuid.UUID
    claim_number: str | None
    status: ClaimStatus
    service_from: date | None
    service_to: date | None
    created_at: datetime
    updated_at: datetime


class ClaimVisitAttachRequest(BaseModel):
    visit_ids: list[uuid.UUID] = Field(default_factory=list)


class ClaimProcedureInput(BaseModel):
    procedure_code_id: uuid.UUID
    units: int = Field(default=1, ge=1)
    modifier: str | None = None
    price: float | None = None


class ClaimProcedureCreateRequest(BaseModel):
    procedures: list[ClaimProcedureInput] = Field(default_factory=list)


class ClaimProcedureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_id: uuid.UUID
    procedure_code_id: uuid.UUID
    units: int
    modifier: str | None
    price: float | None
    created_at: datetime
    updated_at: datetime


class ProcedureCodeSummary(BaseModel):
    id: uuid.UUID
    code: str
    title: str | None
    category: str | None


class ClaimPolicyLinkItem(BaseModel):
    procedure_code: ProcedureCodeSummary
    policy_url: str | None
    missing_policy_link: bool
