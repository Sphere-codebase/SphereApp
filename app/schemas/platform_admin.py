"""Platform admin schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClinicAddressInput(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class ClinicCreateRequest(BaseModel):
    name: str
    phone: str | None = None
    address: ClinicAddressInput | None = None


class ClinicCounters(BaseModel):
    doctors_count: int | None = None
    patients_count: int | None = None
    claims_30d: int | None = None


class ClinicDTO(BaseModel):
    id: int
    name: str
    phone: str | None = None
    is_blocked: bool | None = None
    created_at: datetime | None = None
    counters: ClinicCounters | None = None


class ClinicListResponse(BaseModel):
    items: list[ClinicDTO]
    limit: int
    offset: int
    total: int


class ClinicUpdateRequest(BaseModel):
    is_blocked: bool | None = None


class PlatformAuditItem(BaseModel):
    id: int
    created_at: datetime | None
    clinic_id: int
    clinic_name: str | None
    actor_id: int | None
    actor_name: str | None
    actor_role: str | None
    action: str
    entity: str
    entity_id: str | None
    diff_json: dict[str, Any] | None
    request_id: str | None


class PlatformAuditResponse(BaseModel):
    items: list[PlatformAuditItem]
    limit: int
    offset: int
    total: int


class PlatformUsageRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(..., alias="from")
    to: date


class PlatformUsageScope(BaseModel):
    clinic_id: int | None = None


class PlatformUsageKpis(BaseModel):
    claims_created: int
    claims_finalized: int
    pdf_generated: int
    ai_actions: int
    active_clinics: int


class PlatformUsageTimeseries(BaseModel):
    date: date
    count: int


class PlatformUsageTopClinic(BaseModel):
    clinic_id: int
    clinic_name: str
    claims: int
    pdf: int
    ai: int


class PlatformUsageResponse(BaseModel):
    range: PlatformUsageRange
    scope: PlatformUsageScope
    kpis: PlatformUsageKpis
    timeseries: dict[str, list[PlatformUsageTimeseries]]
    top_clinics: list[PlatformUsageTopClinic]
