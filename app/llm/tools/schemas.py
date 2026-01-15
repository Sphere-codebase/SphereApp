"""Tool argument schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchPatientsArgs(BaseModel):
    query: str = Field(..., min_length=1)


class GetPatientArgs(BaseModel):
    patient_id: int


class GetClaimArgs(BaseModel):
    claim_id: int


class ListClaimsArgs(BaseModel):
    patient_id: int


class RequestFormArgs(BaseModel):
    fields: list[dict[str, Any]]


class CreateClaimDraftArgs(BaseModel):
    patient_id: int
    fields: dict[str, Any]
    confirm: bool = False


class UpdateClaimFieldsArgs(BaseModel):
    claim_id: int
    patch: dict[str, Any]
    confirm: bool = False


class GetAccountArgs(BaseModel):
    pass


class TimeNowArgs(BaseModel):
    tz: str = "Asia/Tbilisi"
