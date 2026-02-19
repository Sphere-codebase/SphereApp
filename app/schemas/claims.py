"""Claim schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ClaimPatientInput(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date | None = None


class ClaimCreateRequest(BaseModel):
    patient_id: int | None = None
    patient: ClaimPatientInput | None = None
    session_id: int | None = None
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
    code: str | None = None
    mcp_codes: list[str] = Field(default_factory=list)


class ClaimMcpCodeResponse(BaseModel):
    claim_id: int
    mcp_code: str


class McpCodeSummary(BaseModel):
    code: str
    description: str | None


class DiagnosisCodeSummary(BaseModel):
    code: str
    description: str | None


class ClaimDiagnosisCodeCreateRequest(BaseModel):
    code: str | None = None
    diagnosis_codes: list[str] = Field(default_factory=list)


class ClaimDiagnosisCodeResponse(BaseModel):
    claim_id: int
    diagnosis_code: str


class PatientSummary(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None


class ClaimDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_status: str | None
    updated_at: datetime | None = None
    patient: PatientSummary
    insurance_company_id: int
    service_date: date | None
    mcp_codes: list[McpCodeSummary] = Field(default_factory=list)
    diagnosis_codes: list[DiagnosisCodeSummary] = Field(default_factory=list)


class ClaimPolicyLinkItem(BaseModel):
    mcp_code: McpCodeSummary
    policy_url: str | None
    missing_policy_link: bool


class ClaimPdfIngestResponse(BaseModel):
    claim_id: int
    patient_id: int
    session_id: int | None = None
    patient_name: str
    patient_date_of_birth: date | None
    account_number: str | None
    service_date: date | None
    line_count: int
    total_billed_cents: int
    total_allowed_cents: int
    total_paid_cents: int


class MyClaimItemSchema(BaseModel):
    id: int
    patient_name: str
    date_of_service: date | None
    claim_number: str | None
    policy: str | None
    paid_amount: float
    billed_amount: float
    currency: str | None


class MyClaimsListResponseSchema(BaseModel):
    items: list[MyClaimItemSchema]
    limit: int
    offset: int
    total: int


class ClaimSummaryItem(BaseModel):
    patient_name: str
    date_of_service: date | None
    claim_number: str | None
    policy: str | None
    paid_amount: float
    billed_amount: float
    currency: str | None


class ClaimSummaryListResponse(BaseModel):
    items: list[ClaimSummaryItem]
    limit: int
    offset: int
    total: int


class ClaimFinancialFlag(BaseModel):
    code: str
    severity: Literal["info", "warn", "high"]
    message: str


class ClaimFinancialPrediction(BaseModel):
    mcp_code: str
    predicted_paid_amount: float
    confidence: float | None = None
    explanation: str | None = None
    source: Literal["ml_predictions", "mcp_payment_predictions"]


class ClaimFinancialSummary(BaseModel):
    claim_id: int
    currency: Literal["USD"]
    predicted_total_paid_amount: float
    predicted_per_mcp: list[ClaimFinancialPrediction] = Field(default_factory=list)
    flags: list[ClaimFinancialFlag] = Field(default_factory=list)
    updated_at: datetime
