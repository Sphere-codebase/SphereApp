"""Patient endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep
from app.core import policy
from app.core.security import get_current_user
from app.db.models import Claim, InsuranceCompany, Patient, User
from app.db.session import get_db
from app.repositories.patients import list_patients_paginated
from app.schemas.patients import (
    NewPatientCreateRequest,
    NewPatientCreateResponse,
    PatientCreateRequest,
    PatientClaimsResponse,
    PatientDetailResponse,
    PatientListItem,
    PatientListResponse,
    PatientResponse,
    PatientUpdateRequest,
)
from app.services.patients import PatientService

router = APIRouter(prefix="/api/patients", tags=["patients"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _get_patient_or_404(db: Session, patient_id: int, current_user: User) -> Patient:
    filters = [Patient.id == patient_id]
    filters.extend(policy.patient_scope_filters(current_user, Patient))
    patient = db.execute(select(Patient).where(*filters)).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("", response_model=PatientListResponse)
def list_patients(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    query: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientListResponse:
    search = query.strip() if query else None
    role = policy.role_for(current_user)
    doctor_id = current_user.id if role == policy.Role.DOCTOR else None
    rows, total = list_patients_paginated(
        db,
        clinic_id=current_user.clinic_id,
        doctor_id=doctor_id,
        query=search,
        limit=limit,
        offset=offset,
    )
    items = [
        PatientListItem(
            id=patient.id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
            chart_number=patient.chart_number,
            primary_phone=patient.primary_phone,
            doctor_id=patient.doctor_id,
            doctor_name=doctor_name,
        )
        for patient, doctor_name in rows
    ]
    return PatientListResponse(items=items, limit=limit, offset=offset, total=total)


@router.post("", response_model=NewPatientCreateResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: NewPatientCreateRequest | PatientCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> NewPatientCreateResponse:
    if not policy.can(current_user, policy.Action.CREATE, policy.Resource.PATIENT):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if isinstance(payload, PatientCreateRequest):
        patient_name = " ".join(
            part for part in [payload.first_name.strip(), payload.last_name.strip()] if part
        ).strip()
        payload = NewPatientCreateRequest(patient_name=patient_name)
    service = PatientService(db)
    response = service.create_new_patient(current_user=current_user, payload=payload)
    audit.log_event(
        action="CREATE",
        entity="patient",
        entity_id=response.id,
        actor=current_user,
        clinic_id=response.clinic_id,
        target_clinic_id=response.clinic_id,
        diff={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return response


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientDetailResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    address = None
    if patient.address is not None:
        address = {
            "line1": patient.address.line1,
            "line2": patient.address.line2,
            "city": patient.address.city,
            "state": patient.address.state,
            "zip": patient.address.zip,
            "country": patient.address.country,
        }
    return PatientDetailResponse(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        chart_number=patient.chart_number,
        primary_phone=patient.primary_phone,
        secondary_phone=patient.secondary_phone,
        address=address,
        doctor_id=patient.doctor_id,
    )


@router.get("/{patient_id}/claims", response_model=PatientClaimsResponse)
def list_patient_claims(
    patient_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientClaimsResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    filters = [
        Claim.patient_id == patient.id,
        Claim.clinic_id == current_user.clinic_id,
    ]
    total = db.execute(select(func.count()).select_from(Claim).where(*filters)).scalar_one()
    rows = (
        db.execute(
            select(Claim, InsuranceCompany.name)
            .join(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
            .where(*filters)
            .order_by(Claim.updated_at.desc().nullslast(), Claim.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .all()
    )
    items = []
    for claim, insurance_name in rows:
        status = "draft"
        if claim.claim_status and claim.claim_status.upper() == "FINAL":
            status = "final"
        items.append(
            {
                "id": claim.id,
                "service_date": claim.service_date,
                "claim_status": status,
                "insurance_company_name": insurance_name,
                "updated_at": claim.updated_at or claim.created_at,
            }
        )
    return PatientClaimsResponse(items=items, limit=limit, offset=offset, total=total)


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    payload: PatientUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> PatientResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.PATIENT, patient):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(patient, field, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    audit.log_event(
        action="UPDATE",
        entity="patient",
        entity_id=patient.id,
        actor=current_user,
        clinic_id=patient.clinic_id,
        target_clinic_id=patient.clinic_id,
        diff={"fields": list(data.keys())},
    )
    return PatientResponse.model_validate(patient)
