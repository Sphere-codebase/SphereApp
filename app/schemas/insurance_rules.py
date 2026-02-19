"""Insurance rules and overrides schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PolicyLinkItem(BaseModel):
    id: int
    insurance_company_id: int
    mcp_code: str
    policy_url: str


class PolicyLinkListResponse(BaseModel):
    items: list[PolicyLinkItem]


class PolicyRulesResponse(BaseModel):
    policy_link_id: int
    extracted_at: datetime | None
    rules_json: Any | None


class OverrideResponseBase(BaseModel):
    policy_link_id: int
    override_json: dict[str, Any] | None
    updated_at: datetime | None


class ClinicOverrideResponse(OverrideResponseBase):
    clinic_id: int


class DoctorOverrideResponse(OverrideResponseBase):
    doctor_id: int


class OverrideUpsertRequest(BaseModel):
    override_json: dict[str, Any]
