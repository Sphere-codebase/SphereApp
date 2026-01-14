"""Patient and visit endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Patient, User, Visit
from app.db.session import get_db
from app.schemas.patients import (
    PatientCreateRequest,
    PatientResponse,
    PatientUpdateRequest,
    VisitCreateRequest,
    VisitResponse,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _get_patient_or_404(
    db: Session, patient_id: uuid.UUID, current_user: User
) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.tenant_id == current_user.tenant_id,
            Patient.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get("", response_model=list[PatientResponse])
def list_patients(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[PatientResponse]:
    stmt = select(Patient).where(
        Patient.tenant_id == current_user.tenant_id,
        Patient.user_id == current_user.id,
    )
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                Patient.full_name.ilike(like),
            )
        )
    patients = db.execute(stmt.order_by(Patient.last_name.asc())).scalars().all()
    return [PatientResponse.model_validate(patient) for patient in patients]


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    full_name = f"{payload.first_name} {payload.last_name}".strip()
    patient = Patient(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        full_name=full_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "first_name" in data or "last_name" in data:
        first = data.get("first_name", patient.first_name) or ""
        last = data.get("last_name", patient.last_name) or ""
        patient.full_name = f"{first} {last}".strip()
    for field, value in data.items():
        setattr(patient, field, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}/visits", response_model=list[VisitResponse])
def list_visits(
    patient_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[VisitResponse]:
    _get_patient_or_404(db, patient_id, current_user)
    visits = (
        db.execute(
            select(Visit).where(
                Visit.patient_id == patient_id,
                Visit.tenant_id == current_user.tenant_id,
            )
        )
        .scalars()
        .all()
    )
    return [VisitResponse.model_validate(visit) for visit in visits]


@router.post(
    "/{patient_id}/visits",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_visit(
    patient_id: uuid.UUID,
    payload: VisitCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> VisitResponse:
    _get_patient_or_404(db, patient_id, current_user)
    visit = Visit(
        tenant_id=current_user.tenant_id,
        patient_id=patient_id,
        visited_at=payload.visited_at,
        provider=payload.provider,
        notes=payload.notes,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return VisitResponse.model_validate(visit)
