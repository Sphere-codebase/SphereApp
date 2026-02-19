"""Dashboard response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DoctorSummary(BaseModel):
    id: int
    full_name: str | None = None


class DashboardSessionSummary(BaseModel):
    id: int
    title: str | None = None
    updated_at: datetime


class DashboardClaimSummary(BaseModel):
    id: int
    patient_name: str
    service_date: date | None = None
    claim_status: str
    insurance_company_name: str | None = None
    updated_at: datetime


class DoctorDashboardResponse(BaseModel):
    doctor: DoctorSummary
    active_sessions: list[DashboardSessionSummary]
    recent_claims: list[DashboardClaimSummary]
