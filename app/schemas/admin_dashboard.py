"""Admin dashboard schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AdminPatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None
    created_at: datetime | None


class AdminInsuranceCompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime | None


class AdminDiagnosisCodeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None


class AdminClaimSummary(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    insurance_company_id: int
    insurance_company_name: str | None
    claim_number: str | None
    claim_status: str | None
    service_date: date | None
    claim_date: date | None
    submitted_at: datetime | None
    billed_amount_total: float | None
    allowed_amount_total: float | None
    coinsurance_amount_total: float | None
    copay_amount_total: float | None
    deductible_amount_total: float | None
    stedi_status: str | None
    stedi_status_code: str | None
    stedi_status_category: str | None
    stedi_status_message: str | None
    stedi_amount_paid: float | None
    stedi_checked_at: datetime | None
    stedi_payer_claim_number: str | None
    created_at: datetime | None


class McpCodeSummary(BaseModel):
    code: str
    description: str | None


class AdminClaimProcedureFactResponse(BaseModel):
    id: int
    mcp_code: McpCodeSummary
    service_date: date | None
    units: float | None
    modifier: str | None
    billed_amount: float | None
    allowed_amount: float | None
    coinsurance_amount: float | None
    copay_amount: float | None
    deductible_amount: float | None
    paid_amount: float | None
    paid_at: date | None
    created_at: datetime | None


class AdminClaimDetailResponse(BaseModel):
    id: int
    patient: AdminPatientSummary
    insurance_company: AdminInsuranceCompanySummary | None
    claim_number: str | None
    claim_status: str | None
    service_date: date | None
    claim_date: date | None
    submitted_at: datetime | None
    billed_amount_total: float | None
    allowed_amount_total: float | None
    coinsurance_amount_total: float | None
    copay_amount_total: float | None
    deductible_amount_total: float | None
    stedi_status: str | None
    stedi_status_code: str | None
    stedi_status_category: str | None
    stedi_status_message: str | None
    stedi_amount_paid: float | None
    stedi_checked_at: datetime | None
    stedi_payer_claim_number: str | None
    created_at: datetime | None
    procedures: list[AdminClaimProcedureFactResponse]
    diagnoses: list[AdminDiagnosisCodeSummary]
