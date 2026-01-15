"""Claim schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ClaimCreateRequest(BaseModel):
    patient_id: int
    insurance_company_id: int
    claim_number: str | None = None
    claim_status: str | None = None
    service_date: date | None = None
    claim_date: date | None = None
    billed_amount_total: float | None = None
    allowed_amount_total: float | None = None
    coinsurance_amount_total: float | None = None
    copay_amount_total: float | None = None
    deductible_amount_total: float | None = None


class ClaimUpdateRequest(BaseModel):
    patient_id: int | None = None
    insurance_company_id: int | None = None
    claim_number: str | None = None
    claim_status: str | None = None
    service_date: date | None = None
    claim_date: date | None = None
    billed_amount_total: float | None = None
    allowed_amount_total: float | None = None
    coinsurance_amount_total: float | None = None
    copay_amount_total: float | None = None
    deductible_amount_total: float | None = None


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    insurance_company_id: int
    service_date: date | None
    created_at: datetime | None
    claim_number: str | None
    claim_status: str | None
    claim_date: date | None
    billed_amount_total: float | None
    allowed_amount_total: float | None
    coinsurance_amount_total: float | None
    copay_amount_total: float | None
    deductible_amount_total: float | None


class ClaimMcpCodeCreateRequest(BaseModel):
    mcp_codes: list[str] = Field(default_factory=list)


class ClaimMcpCodeResponse(BaseModel):
    claim_id: int
    mcp_code: str


class McpCodeSummary(BaseModel):
    code: str
    description: str | None


class ClaimPolicyLinkItem(BaseModel):
    mcp_code: McpCodeSummary
    policy_url: str | None
    missing_policy_link: bool
