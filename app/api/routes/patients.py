"""Patient endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep
from app.core import policy
from app.core.security import get_current_user
from app.db.models import Patient, User
from app.db.session import get_db
from app.repositories.patients import list_patients_query
from app.schemas.patients import (
    NewPatientCreateRequest,
    NewPatientCreateResponse,
    PatientCreateRequest,
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


@router.get("", response_model=list[PatientResponse])
def list_patients(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[PatientResponse]:
    role = policy.role_for(current_user)
    clinic_id = None if role == policy.Role.PLATFORM_STAFF_ADMIN else current_user.clinic_id
    doctor_id = current_user.id if role == policy.Role.DOCTOR else None
    patients = list_patients_query(db, clinic_id=clinic_id, doctor_id=doctor_id, query=query)
    return [PatientResponse.model_validate(patient) for patient in patients]


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
