"""Admin dashboard schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import ClaimStatus


class AdminPatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    first_name: str | None
    last_name: str | None
    full_name: str
    date_of_birth: date | None
    sex: str | None
    created_at: datetime
    updated_at: datetime


class AdminAgencySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminDiagnosisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str | None


class AdminClaimSummary(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    patient_user_id: uuid.UUID | None
    agency_id: uuid.UUID | None
    agency_name: str | None
    claim_number: str | None
    status: ClaimStatus
    service_from: date | None
    service_to: date | None
    received_at: datetime | None
    finalized_at: datetime | None
    billed_total_cents: int | None
    allowed_total_cents: int | None
    paid_total_cents: int | None
    patient_responsibility_cents: int | None
    created_at: datetime
    updated_at: datetime


class ProcedureCodeSummary(BaseModel):
    id: uuid.UUID
    code: str
    title: str | None
    category: str | None


class AdminClaimProcedurePaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    paid_amount_cents: int
    adjustment_amount_cents: int | None
    adjustment_reason_code: str | None
    check_number: str | None
    paid_at: datetime
    created_at: datetime


class AdminClaimProcedureResponse(BaseModel):
    id: uuid.UUID
    procedure_code: ProcedureCodeSummary
    units: int
    modifier: str | None
    price: float | None
    billed_amount_cents: int | None
    allowed_amount_cents: int | None
    coinsurance_amount_cents: int | None
    copay_amount_cents: int | None
    deductible_amount_cents: int | None
    paid_amount_cents: int | None
    denial_reason_code: str | None
    line_number: int | None
    created_at: datetime
    updated_at: datetime
    payments: list[AdminClaimProcedurePaymentResponse]


class AdminClaimDetailResponse(BaseModel):
    id: uuid.UUID
    patient: AdminPatientSummary
    agency: AdminAgencySummary | None
    claim_number: str | None
    status: ClaimStatus
    service_from: date | None
    service_to: date | None
    received_at: datetime | None
    finalized_at: datetime | None
    billed_total_cents: int | None
    allowed_total_cents: int | None
    paid_total_cents: int | None
    patient_responsibility_cents: int | None
    created_at: datetime
    updated_at: datetime
    procedures: list[AdminClaimProcedureResponse]
    diagnoses: list[AdminDiagnosisSummary]
