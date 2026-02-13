"""Patient endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.id_utils import next_id
from app.db.models import Patient, User
from app.db.session import get_db
from app.repositories.patients import list_patients_query
from app.schemas.patients import (
    PatientCreateRequest,
    PatientResponse,
    PatientUpdateRequest,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/patients", tags=["patients"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _get_patient_or_404(db: Session, patient_id: int, current_user: User) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.doctor_id == current_user.id,
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
    patients = list_patients_query(db, doctor_id=current_user.id, query=query)
    return [PatientResponse.model_validate(patient) for patient in patients]


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    patient = Patient(
        id=next_id(db, Patient),
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        created_at=utcnow(),
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    payload: PatientUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PatientResponse:
    patient = _get_patient_or_404(db, patient_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(patient, field, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return PatientResponse.model_validate(patient)
