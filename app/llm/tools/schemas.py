"""Tool argument schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class SearchPatientsArgs(BaseModel):
    query: str = Field(..., min_length=1)


class GetPatientArgs(BaseModel):
    patient_id: uuid.UUID


class GetClaimArgs(BaseModel):
    claim_id: uuid.UUID


class ListClaimsArgs(BaseModel):
    patient_id: uuid.UUID


class RequestFormArgs(BaseModel):
    fields: list[dict[str, Any]]


class CreateClaimDraftArgs(BaseModel):
    patient_id: uuid.UUID
    fields: dict[str, Any]
    confirm: bool = False


class UpdateClaimFieldsArgs(BaseModel):
    claim_id: uuid.UUID
    patch: dict[str, Any]
    confirm: bool = False
