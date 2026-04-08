"""Dashboard endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep, require_roles
from app.core import policy
from app.db.models import ChatMessage, ChatSession, Claim, InsuranceCompany, Patient
from app.db.session import get_db
from app.schemas.dashboard import (
    DashboardClaimSummary,
    DashboardSessionSummary,
    DoctorDashboardResponse,
    DoctorSummary,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
DbSessionDep = Annotated[Session, Depends(get_db)]


def _normalize_claim_status(value: str | None) -> str:
    if value and value.upper() == "FINAL":
        return "final"
    return "draft"


@router.get(
    "/doctor",
    response_model=DoctorDashboardResponse,
    dependencies=[Depends(require_roles("doctor", "chief_doctor", "clinic_admin"))],
)
def doctor_dashboard(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    limit_sessions: Annotated[int, Query(ge=1, le=50)] = 8,
    limit_claims: Annotated[int, Query(ge=1, le=50)] = 8,
) -> DoctorDashboardResponse:
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    message_updates = (
        select(
            ChatMessage.session_id.label("session_id"),
            func.max(ChatMessage.created_at).label("last_message_at"),
        )
        .where(ChatMessage.clinic_id == current_user.clinic_id)
        .group_by(ChatMessage.session_id)
        .subquery()
    )

    session_updated_at = func.coalesce(message_updates.c.last_message_at, ChatSession.created_at)
    session_rows = db.execute(
        select(ChatSession, session_updated_at.label("updated_at"))
        .outerjoin(message_updates, message_updates.c.session_id == ChatSession.id)
        .where(
            ChatSession.clinic_id == current_user.clinic_id,
            ChatSession.doctor_id == current_user.id,
            ChatSession.status == "open",
        )
        .order_by(session_updated_at.desc())
        .limit(limit_sessions)
    ).all()
    active_sessions = [
        DashboardSessionSummary(
            id=session.id,
            title=session.title,
            updated_at=updated_at,
        )
        for session, updated_at in session_rows
    ]

    claim_updated_at = func.coalesce(Claim.updated_at, Claim.created_at)
    claim_rows = db.execute(
        select(Claim, Patient, InsuranceCompany, claim_updated_at.label("updated_at"))
        .join(Patient, Claim.patient_id == Patient.id)
        .outerjoin(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
        .where(
            Claim.clinic_id == current_user.clinic_id,
            Claim.doctor_id == current_user.id,
        )
        .order_by(claim_updated_at.desc())
        .limit(limit_claims)
    ).all()
    recent_claims: list[DashboardClaimSummary] = []
    for claim, patient, company, updated_at in claim_rows:
        patient_name = " ".join(
            part for part in [patient.first_name or "", patient.last_name or ""] if part
        ).strip()
        recent_claims.append(
            DashboardClaimSummary(
                id=claim.id,
                patient_name=patient_name or "Unknown",
                service_date=claim.service_date,
                claim_status=_normalize_claim_status(claim.claim_status),
                insurance_company_name=company.name if company else None,
                updated_at=updated_at,
            )
        )

    return DoctorDashboardResponse(
        doctor=DoctorSummary(id=current_user.id, full_name=current_user.full_name),
        active_sessions=active_sessions,
        recent_claims=recent_claims,
    )
