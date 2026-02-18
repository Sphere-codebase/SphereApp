"""Patient schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PatientPhoneInput(BaseModel):
    primary: str | None = None
    secondary: str | None = None


class PatientAddressInput(BaseModel):
    line1: str = Field(..., min_length=1)
    line2: str | None = None
    city: str = Field(..., min_length=1)
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class InsuranceCardInput(BaseModel):
    storage_key: str = Field(..., min_length=1)
    side: str = Field(..., pattern="^(front|back)$")
    content_type: str | None = None
    size_bytes: int | None = Field(None, ge=0)


class PatientInsuranceInput(BaseModel):
    priority: str = Field(..., pattern="^(primary|secondary)$")
    insurance_company_id: int
    member_id: str | None = None
    policy_type: str | None = None
    copay_amount: float | None = None
    deductible_amount: float | None = None
    currency: str | None = None
    card: InsuranceCardInput | None = None


class NewPatientCreateRequest(BaseModel):
    patient_name: str = Field(..., min_length=1)
    chart_number: str | None = None
    provider_name: str | None = None
    gender: str | None = None
    phones: PatientPhoneInput = Field(default_factory=PatientPhoneInput)
    address: PatientAddressInput | None = None
    insurances: list[PatientInsuranceInput] | None = None


class InsuranceCardResponse(BaseModel):
    side: str
    storage_key: str
    content_type: str | None
    size_bytes: int | None
    uploaded_at: datetime | None


class PatientInsuranceResponse(BaseModel):
    priority: str
    insurance_company_id: int
    member_id: str | None
    policy_type: str | None
    copay_amount: float | None
    deductible_amount: float | None
    currency: str | None
    cards: list[InsuranceCardResponse]


class PatientAddressResponse(BaseModel):
    line1: str
    line2: str | None
    city: str
    state: str | None
    zip: str | None
    country: str | None


class NewPatientCreateResponse(BaseModel):
    id: int
    clinic_id: int
    first_name: str | None
    last_name: str | None
    chart_number: str | None
    provider_name: str | None
    gender: str | None
    phones: PatientPhoneInput
    address: PatientAddressResponse | None
    insurances: list[PatientInsuranceResponse]
    created_at: datetime | None


class PatientCreateRequest(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    date_of_birth: date | None = None


class PatientUpdateRequest(BaseModel):
    first_name: str | None = Field(None, min_length=1)
    last_name: str | None = Field(None, min_length=1)
    date_of_birth: date | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None
    created_at: datetime | None


class InsuranceCompanyListItem(BaseModel):
    id: int
    name: str


class InsuranceCompanyListResponse(BaseModel):
    items: list[InsuranceCompanyListItem]
    limit: int
    offset: int
    total: int
