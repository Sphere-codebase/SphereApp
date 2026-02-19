"""Clinic admin endpoints."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, CurrentUserDep, require_roles
from app.db.models import AuditLog, Claim, InsuranceCompany, User
from app.db.session import get_db
from app.utils.audit_export import diff_to_json, iter_csv
from app.schemas.clinic_admin import (
    AuditLogItemDTO,
    AuditLogListResponse,
    ClinicDashboardInsurer,
    ClinicDashboardKpis,
    ClinicDashboardRange,
    ClinicDashboardResponse,
    ClinicDashboardTimeseries,
    DoctorListResponse,
    DoctorUpdateRequest,
    DoctorUserDTO,
)

router = APIRouter(prefix="/api/clinic", tags=["clinic_admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]


def _date_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=30)
    return date_from, date_to


@router.get("/dashboard", response_model=ClinicDashboardResponse)
def clinic_dashboard(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> ClinicDashboardResponse:
    require_roles("chief_doctor", "clinic_admin")(current_user)
    start_date, end_date = _date_range(date_from, date_to)
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    claim_filters = [
        Claim.clinic_id == current_user.clinic_id,
        Claim.created_at >= start_dt,
        Claim.created_at <= end_dt,
    ]

    total_claims = db.execute(select(func.count()).select_from(Claim).where(*claim_filters)).scalar_one()
    draft_claims = db.execute(
        select(func.count()).select_from(Claim).where(
            *claim_filters,
            func.upper(Claim.claim_status) == "DRAFT",
        )
    ).scalar_one()
    finalized_claims = db.execute(
        select(func.count()).select_from(Claim).where(
            *claim_filters,
            func.upper(Claim.claim_status) == "FINAL",
        )
    ).scalar_one()

    active_doctors = db.execute(
        select(func.count()).select_from(User).where(
            User.clinic_id == current_user.clinic_id,
            User.is_active.is_(True),
            User.role.in_(["doctor", "chief_doctor", "clinic_admin"]),
        )
    ).scalar_one()

    top_insurers_rows = (
        db.execute(
            select(Claim.insurance_company_id, InsuranceCompany.name, func.count())
            .join(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
            .where(*claim_filters)
            .group_by(Claim.insurance_company_id, InsuranceCompany.name)
            .order_by(func.count().desc())
            .limit(5)
        )
        .all()
    )
    top_insurers = [
        ClinicDashboardInsurer(
            insurance_company_id=company_id,
            name=company_name,
            claim_count=count,
        )
        for company_id, company_name, count in top_insurers_rows
    ]

    claims_series_rows = (
        db.execute(
            select(func.date(Claim.created_at), func.count())
            .where(*claim_filters)
            .group_by(func.date(Claim.created_at))
            .order_by(func.date(Claim.created_at))
        )
        .all()
    )
    claims_timeseries = [
        ClinicDashboardTimeseries(date=row[0], count=row[1]) for row in claims_series_rows
    ]

    ai_filters = [
        AuditLog.clinic_id == current_user.clinic_id,
        AuditLog.created_at >= start_dt,
        AuditLog.created_at <= end_dt,
        AuditLog.action.ilike("ai_%"),
    ]
    ai_series_rows = (
        db.execute(
            select(func.date(AuditLog.created_at), func.count())
            .where(*ai_filters)
            .group_by(func.date(AuditLog.created_at))
            .order_by(func.date(AuditLog.created_at))
        )
        .all()
    )
    ai_timeseries = [
        ClinicDashboardTimeseries(date=row[0], count=row[1]) for row in ai_series_rows
    ]

    recent_rows = (
        db.execute(
            select(AuditLog, User.full_name, User.email, User.role)
            .join(User, User.id == AuditLog.actor_id, isouter=True)
            .where(AuditLog.clinic_id == current_user.clinic_id)
            .order_by(AuditLog.created_at.desc())
            .limit(20)
        )
        .all()
    )
    recent_activity = [
        AuditLogItemDTO(
            id=log.id,
            created_at=log.created_at,
            actor_id=log.actor_id,
            actor_name=full_name or email,
            actor_role=role,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            diff_json=log.diff_json,
            request_id=log.request_id,
        )
        for log, full_name, email, role in recent_rows
    ]

    return ClinicDashboardResponse(
        range=ClinicDashboardRange(from_=start_date, to=end_date),
        kpis=ClinicDashboardKpis(
            total_claims=total_claims,
            draft_claims=draft_claims,
            finalized_claims=finalized_claims,
            active_doctors=active_doctors,
        ),
        top_insurers=top_insurers,
        claims_timeseries=claims_timeseries,
        ai_timeseries=ai_timeseries,
        recent_activity=recent_activity,
    )


@router.get("/doctors", response_model=DoctorListResponse)
def list_clinic_doctors(
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> DoctorListResponse:
    require_roles("chief_doctor", "clinic_admin")(current_user)
    users = (
        db.execute(
            select(User)
            .where(
                User.clinic_id == current_user.clinic_id,
                User.role.in_(["doctor", "chief_doctor", "clinic_admin"]),
            )
            .order_by(User.full_name.asc().nullslast(), User.email.asc())
        )
        .scalars()
        .all()
    )
    items = [
        DoctorUserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=bool(user.is_active),
            created_at=user.created_at,
        )
        for user in users
    ]
    return DoctorListResponse(items=items)


@router.patch("/doctors/{doctor_id}", response_model=DoctorUserDTO)
def update_clinic_doctor(
    doctor_id: int,
    payload: DoctorUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> DoctorUserDTO:
    require_roles("clinic_admin")(current_user)
    user = db.execute(
        select(User).where(
            User.id == doctor_id,
            User.clinic_id == current_user.clinic_id,
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if user.role == "platform_staff_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    before = {"role": user.role, "is_active": bool(user.is_active)}
    changes: dict[str, bool | str] = {}

    if payload.role is not None:
        if payload.role not in {"doctor", "chief_doctor", "clinic_admin"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")
        changes["role"] = payload.role

    if payload.is_active is not None:
        changes["is_active"] = payload.is_active

    if not changes:
        return DoctorUserDTO(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=bool(user.is_active),
            created_at=user.created_at,
        )

    will_remove_admin = False
    if user.role == "clinic_admin":
        if "role" in changes and changes["role"] != "clinic_admin":
            will_remove_admin = True
        if "is_active" in changes and changes["is_active"] is False:
            will_remove_admin = True
    if will_remove_admin:
        active_admins = db.execute(
            select(func.count()).select_from(User).where(
                User.clinic_id == current_user.clinic_id,
                User.role == "clinic_admin",
                User.is_active.is_(True),
            )
        ).scalar_one()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active clinic admin",
            )

    for field, value in changes.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    after = {"role": user.role, "is_active": bool(user.is_active)}
    audit.log_event(
        action="clinic.doctor_updated",
        entity="user",
        entity_id=user.id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={"before": before, "after": after},
        scope="clinic",
        actor_role=current_user.role,
    )

    return DoctorUserDTO(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
        created_at=user.created_at,
    )


@router.get("/audit-logs", response_model=list[AuditLogItemDTO])
def list_clinic_audit_logs(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogItemDTO]:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)

    filters = [AuditLog.clinic_id == current_user.clinic_id]
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if entity:
        filters.append(AuditLog.entity == entity)
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, time.max))

    total = db.execute(select(func.count()).select_from(AuditLog).where(*filters)).scalar_one()

    rows = (
        db.execute(
            select(AuditLog, User.full_name, User.email, User.role)
            .join(User, User.id == AuditLog.actor_id, isouter=True)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .all()
    )

    items = [
        AuditLogItemDTO(
            id=log.id,
            clinic_id=log.clinic_id,
            created_at=log.created_at,
            actor_id=log.actor_id,
            actor_name=full_name or email,
            actor_role=role,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            diff_json=log.diff_json,
            request_id=log.request_id,
        )
        for log, full_name, email, role in rows
    ]

    return items


@router.get("/audit-logs/export")
def export_clinic_audit_logs(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    include_diff: Annotated[int, Query(ge=0, le=1)] = 0,
) -> StreamingResponse:
    require_roles("chief_doctor", "clinic_admin")(current_user)

    filters = [AuditLog.clinic_id == current_user.clinic_id]
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if entity:
        filters.append(AuditLog.entity == entity)
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, time.max))

    rows = (
        db.execute(
            select(AuditLog, User.full_name, User.email, User.role)
            .join(User, User.id == AuditLog.actor_id, isouter=True)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
        )
        .all()
    )

    include_diff_json = bool(include_diff)
    headers = [
        "created_at",
        "actor_id",
        "actor_role",
        "action",
        "entity",
        "entity_id",
        "request_id",
    ]
    if include_diff_json:
        headers.append("diff_json")

    def row_iter():
        for log, full_name, email, role in rows:
            actor_role = log.actor_role or role
            row = [
                log.created_at.isoformat() if log.created_at else "",
                log.actor_id,
                actor_role,
                log.action,
                log.entity,
                log.entity_id,
                log.request_id,
            ]
            if include_diff_json:
                row.append(diff_to_json(log.diff_json))
            yield row

    audit.log_event(
        action="audit.exported",
        entity="audit_logs",
        entity_id=None,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
            "filters": {
                "actor_id": actor_id,
                "action": action,
                "entity": entity,
            },
            "include_diff": include_diff_json,
        },
        scope="clinic",
        actor_role=current_user.role,
    )

    filename = f"clinic_audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter_csv(headers, row_iter()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
