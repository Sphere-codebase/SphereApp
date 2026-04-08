"""Platform admin endpoints."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_platform_staff_admin
from app.db.id_utils import next_id
from app.db.models import AuditLog, Claim, Clinic, Patient, User, Address
from app.db.session import get_db
from app.schemas.platform_admin import (
    ClinicCounters,
    ClinicCreateRequest,
    ClinicDTO,
    ClinicListResponse,
    ClinicUpdateRequest,
    PlatformAuditItem,
    PlatformAuditResponse,
    PlatformUsageKpis,
    PlatformUsageRange,
    PlatformUsageResponse,
    PlatformUsageScope,
    PlatformUsageTimeseries,
    PlatformUsageTopClinic,
)
from app.utils.audit_export import diff_to_json, iter_csv, mask_pii
from app.utils.time import utcnow

router = APIRouter(prefix="/api/platform", tags=["platform_admin"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("/clinics", response_model=ClinicListResponse)
def list_clinics(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ClinicListResponse:
    base_filters = []
    if query:
        like = f"%{query}%"
        base_filters.append(Clinic.name.ilike(like))

    total = db.execute(select(func.count()).select_from(Clinic).where(*base_filters)).scalar_one()

    doctor_subq = (
        select(User.clinic_id, func.count().label("doctors_count"))
        .where(User.role.in_(["doctor", "chief_doctor", "clinic_admin"]))
        .group_by(User.clinic_id)
        .subquery()
    )
    patient_subq = (
        select(Patient.clinic_id, func.count().label("patients_count"))
        .group_by(Patient.clinic_id)
        .subquery()
    )
    window_start = utcnow() - timedelta(days=30)
    claims_subq = (
        select(Claim.clinic_id, func.count().label("claims_30d"))
        .where(Claim.created_at >= window_start)
        .group_by(Claim.clinic_id)
        .subquery()
    )

    rows = db.execute(
        select(
            Clinic,
            doctor_subq.c.doctors_count,
            patient_subq.c.patients_count,
            claims_subq.c.claims_30d,
        )
        .outerjoin(doctor_subq, doctor_subq.c.clinic_id == Clinic.id)
        .outerjoin(patient_subq, patient_subq.c.clinic_id == Clinic.id)
        .outerjoin(claims_subq, claims_subq.c.clinic_id == Clinic.id)
        .where(*base_filters)
        .order_by(Clinic.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = []
    for clinic, doctors_count, patients_count, claims_30d in rows:
        items.append(
            ClinicDTO(
                id=clinic.id,
                name=clinic.name,
                phone=clinic.phone,
                is_blocked=clinic.is_blocked,
                created_at=clinic.created_at,
                counters=ClinicCounters(
                    doctors_count=doctors_count or 0,
                    patients_count=patients_count or 0,
                    claims_30d=claims_30d or 0,
                ),
            )
        )

    return ClinicListResponse(items=items, limit=limit, offset=offset, total=total)


@router.post("/clinics", response_model=ClinicDTO, status_code=status.HTTP_201_CREATED)
def create_clinic(
    payload: ClinicCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> ClinicDTO:
    address_id = None
    if payload.address is not None:
        if not payload.address.line1 or not payload.address.city:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Address requires line1 and city",
            )
        address = Address(
            id=next_id(db, Address),
            line1=payload.address.line1,
            line2=payload.address.line2,
            city=payload.address.city,
            state=payload.address.state,
            zip=payload.address.zip,
            country=payload.address.country,
            created_at=utcnow(),
        )
        db.add(address)
        db.flush()
        address_id = address.id

    clinic = Clinic(
        id=next_id(db, Clinic),
        name=payload.name,
        phone=payload.phone,
        address_id=address_id,
        is_blocked=False,
        created_at=utcnow(),
    )
    db.add(clinic)
    db.commit()
    db.refresh(clinic)

    audit.log_event(
        action="platform.clinic_created",
        entity="clinic",
        entity_id=clinic.id,
        actor=current_user,
        clinic_id=clinic.id,
        diff={"name": clinic.name, "phone": clinic.phone},
        scope="platform",
        actor_role=current_user.role,
    )

    return ClinicDTO(
        id=clinic.id,
        name=clinic.name,
        phone=clinic.phone,
        is_blocked=clinic.is_blocked,
        created_at=clinic.created_at,
        counters=ClinicCounters(doctors_count=0, patients_count=0, claims_30d=0),
    )


@router.patch("/clinics/{clinic_id}", response_model=ClinicDTO)
def update_clinic(
    clinic_id: int,
    payload: ClinicUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> ClinicDTO:
    clinic = db.execute(select(Clinic).where(Clinic.id == clinic_id)).scalar_one_or_none()
    if clinic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found")

    before = {"is_blocked": clinic.is_blocked}
    updated = False
    if payload.is_blocked is not None:
        clinic.is_blocked = payload.is_blocked
        clinic.updated_at = utcnow()
        updated = True

    if updated:
        db.add(clinic)
        db.commit()
        db.refresh(clinic)
        audit.log_event(
            action="platform.clinic_updated",
            entity="clinic",
            entity_id=clinic.id,
            actor=current_user,
            clinic_id=clinic.id,
            diff={"before": before, "after": {"is_blocked": clinic.is_blocked}},
            scope="platform",
            actor_role=current_user.role,
        )

    return ClinicDTO(
        id=clinic.id,
        name=clinic.name,
        phone=clinic.phone,
        is_blocked=clinic.is_blocked,
        created_at=clinic.created_at,
        counters=None,
    )


@router.get("/audit", response_model=PlatformAuditResponse)
def list_platform_audit(
    db: DbSessionDep,
    current_user: AdminUserDep,
    clinic_id: Annotated[int | None, Query()] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    entity: Annotated[str | None, Query()] = None,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlatformAuditResponse:
    filters = []
    if clinic_id is not None:
        filters.append(AuditLog.clinic_id == clinic_id)
    if entity:
        filters.append(AuditLog.entity == entity)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, time.max))

    total = db.execute(select(func.count()).select_from(AuditLog).where(*filters)).scalar_one()

    rows = db.execute(
        select(AuditLog, Clinic.name, User.full_name, User.email, User.role)
        .join(Clinic, Clinic.id == AuditLog.clinic_id, isouter=True)
        .join(User, User.id == AuditLog.actor_id, isouter=True)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = []
    for log, clinic_name, full_name, email, role in rows:
        items.append(
            PlatformAuditItem(
                id=log.id,
                created_at=log.created_at,
                clinic_id=log.clinic_id,
                clinic_name=clinic_name,
                actor_id=log.actor_id,
                actor_name=full_name or email,
                actor_role=role,
                action=log.action,
                entity=log.entity,
                entity_id=log.entity_id,
                diff_json=mask_pii(log.diff_json) if log.diff_json else None,
                request_id=log.request_id,
            )
        )

    return PlatformAuditResponse(items=items, limit=limit, offset=offset, total=total)


@router.get("/audit/export")
def export_platform_audit_logs(
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
    actor_id: Annotated[int | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    entity: Annotated[str | None, Query()] = None,
    clinic_id: Annotated[int | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    include_diff: Annotated[int, Query(ge=0, le=1)] = 0,
) -> StreamingResponse:
    filters = []
    if clinic_id is not None:
        filters.append(AuditLog.clinic_id == clinic_id)
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

    rows = db.execute(
        select(AuditLog, Clinic.name, User.full_name, User.email, User.role)
        .join(Clinic, Clinic.id == AuditLog.clinic_id)
        .join(User, User.id == AuditLog.actor_id, isouter=True)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
    ).all()

    include_diff_json = bool(include_diff)
    headers = [
        "created_at",
        "clinic_id",
        "clinic_name",
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
        for log, clinic_name, full_name, email, role in rows:
            actor_role = log.actor_role or role
            row = [
                log.created_at.isoformat() if log.created_at else "",
                log.clinic_id,
                clinic_name,
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
                "clinic_id": clinic_id,
            },
            "include_diff": include_diff_json,
        },
        scope="platform",
        actor_role=current_user.role,
    )

    filename = f"platform_audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter_csv(headers, row_iter()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _usage_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=30)
    return date_from, date_to


@router.get("/usage", response_model=PlatformUsageResponse)
def platform_usage(
    db: DbSessionDep,
    current_user: AdminUserDep,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    clinic_id: Annotated[int | None, Query()] = None,
) -> PlatformUsageResponse:
    start_date, end_date = _usage_range(date_from, date_to)
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    claim_filters = [Claim.created_at >= start_dt, Claim.created_at <= end_dt]
    if clinic_id is not None:
        claim_filters.append(Claim.clinic_id == clinic_id)

    claims_created = db.execute(
        select(func.count()).select_from(Claim).where(*claim_filters)
    ).scalar_one()

    finalized_filters = [
        func.upper(Claim.claim_status) == "FINAL",
        func.coalesce(Claim.updated_at, Claim.created_at) >= start_dt,
        func.coalesce(Claim.updated_at, Claim.created_at) <= end_dt,
    ]
    if clinic_id is not None:
        finalized_filters.append(Claim.clinic_id == clinic_id)
    claims_finalized = db.execute(
        select(func.count()).select_from(Claim).where(*finalized_filters)
    ).scalar_one()

    audit_filters = [
        AuditLog.created_at >= start_dt,
        AuditLog.created_at <= end_dt,
    ]
    if clinic_id is not None:
        audit_filters.append(AuditLog.clinic_id == clinic_id)

    pdf_generated = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            *audit_filters,
            AuditLog.action == "claim.pdf_generated",
        )
    ).scalar_one()

    ai_actions = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            *audit_filters,
            AuditLog.action.ilike("ai_%"),
        )
    ).scalar_one()

    active_filters = [Clinic.is_blocked.is_(False)]
    if clinic_id is not None:
        active_filters.append(Clinic.id == clinic_id)
    active_clinics = db.execute(
        select(func.count()).select_from(Clinic).where(*active_filters)
    ).scalar_one()

    claims_series_rows = db.execute(
        select(func.date(Claim.created_at), func.count())
        .where(*claim_filters)
        .group_by(func.date(Claim.created_at))
        .order_by(func.date(Claim.created_at))
    ).all()
    claims_series = [
        PlatformUsageTimeseries(date=row[0], count=row[1]) for row in claims_series_rows
    ]

    pdf_series_rows = db.execute(
        select(func.date(AuditLog.created_at), func.count())
        .where(*audit_filters, AuditLog.action == "claim.pdf_generated")
        .group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
    ).all()
    pdf_series = [PlatformUsageTimeseries(date=row[0], count=row[1]) for row in pdf_series_rows]

    ai_series_rows = db.execute(
        select(func.date(AuditLog.created_at), func.count())
        .where(*audit_filters, AuditLog.action.ilike("ai_%"))
        .group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
    ).all()
    ai_series = [PlatformUsageTimeseries(date=row[0], count=row[1]) for row in ai_series_rows]

    claims_subq = (
        select(Claim.clinic_id, func.count().label("claims"))
        .where(*claim_filters)
        .group_by(Claim.clinic_id)
        .subquery()
    )
    pdf_subq = (
        select(AuditLog.clinic_id, func.count().label("pdf"))
        .where(*audit_filters, AuditLog.action == "claim.pdf_generated")
        .group_by(AuditLog.clinic_id)
        .subquery()
    )
    ai_subq = (
        select(AuditLog.clinic_id, func.count().label("ai"))
        .where(*audit_filters, AuditLog.action.ilike("ai_%"))
        .group_by(AuditLog.clinic_id)
        .subquery()
    )

    top_filters = []
    if clinic_id is not None:
        top_filters.append(Clinic.id == clinic_id)

    top_rows = db.execute(
        select(
            Clinic.id,
            Clinic.name,
            func.coalesce(claims_subq.c.claims, 0),
            func.coalesce(pdf_subq.c.pdf, 0),
            func.coalesce(ai_subq.c.ai, 0),
        )
        .outerjoin(claims_subq, claims_subq.c.clinic_id == Clinic.id)
        .outerjoin(pdf_subq, pdf_subq.c.clinic_id == Clinic.id)
        .outerjoin(ai_subq, ai_subq.c.clinic_id == Clinic.id)
        .where(*top_filters)
        .order_by(func.coalesce(claims_subq.c.claims, 0).desc())
        .limit(10)
    ).all()

    top_clinics = [
        PlatformUsageTopClinic(
            clinic_id=row[0],
            clinic_name=row[1],
            claims=row[2],
            pdf=row[3],
            ai=row[4],
        )
        for row in top_rows
    ]

    return PlatformUsageResponse(
        range=PlatformUsageRange(from_=start_date, to=end_date),
        scope=PlatformUsageScope(clinic_id=clinic_id),
        kpis=PlatformUsageKpis(
            claims_created=claims_created,
            claims_finalized=claims_finalized,
            pdf_generated=pdf_generated,
            ai_actions=ai_actions,
            active_clinics=active_clinics,
        ),
        timeseries={"claims": claims_series, "pdf": pdf_series, "ai": ai_series},
        top_clinics=top_clinics,
    )
