"""Patient repository helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Patient
from app.utils.time import utcnow


def upsert_patient(
    db: Session,
    *,
    doctor_id: int,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: date | None,
) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.doctor_id == doctor_id,
            Patient.first_name == first_name,
            Patient.last_name == last_name,
            Patient.date_of_birth == date_of_birth,
        )
    ).scalar_one_or_none()
    if patient is not None:
        return patient

    patient = Patient(
        id=next_id(db, Patient),
        doctor_id=doctor_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        created_at=utcnow(),
    )
    db.add(patient)
    return patient
