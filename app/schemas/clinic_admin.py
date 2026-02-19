"""Clinic admin schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DoctorUserDTO(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime | None = None


class DoctorListResponse(BaseModel):
    items: list[DoctorUserDTO]


class DoctorUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AuditLogItemDTO(BaseModel):
    id: int
    clinic_id: int
    created_at: datetime | None
    actor_id: int | None
    actor_name: str | None
    actor_role: str | None
    action: str
    entity: str
    entity_id: str | None
    diff_json: dict[str, Any] | None
    request_id: str | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItemDTO]
    limit: int
    offset: int
    total: int


class ClinicDashboardKpis(BaseModel):
    total_claims: int
    draft_claims: int
    finalized_claims: int
    active_doctors: int


class ClinicDashboardInsurer(BaseModel):
    insurance_company_id: int
    name: str
    claim_count: int


class ClinicDashboardTimeseries(BaseModel):
    date: date
    count: int


class ClinicDashboardRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(..., alias="from")
    to: date


class ClinicDashboardResponse(BaseModel):
    range: ClinicDashboardRange
    kpis: ClinicDashboardKpis
    top_insurers: list[ClinicDashboardInsurer]
    claims_timeseries: list[ClinicDashboardTimeseries]
    ai_timeseries: list[ClinicDashboardTimeseries]
    recent_activity: list[AuditLogItemDTO]
