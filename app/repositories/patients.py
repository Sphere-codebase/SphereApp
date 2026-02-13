"""Patient repository helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Patient
from app.utils.time import utcnow


def upsert_patient(
    db: Session,
    *,
    doctor_id: int,
    clinic_id: int | None = None,
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
        clinic_id=clinic_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        created_at=utcnow(),
    )
    db.add(patient)
    return patient


def list_patients_query(db: Session, *, doctor_id: int | None, query: str | None) -> list[Patient]:
    stmt = select(Patient)
    if doctor_id is not None:
        stmt = stmt.where(Patient.doctor_id == doctor_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
            )
        )
    return db.execute(stmt.order_by(Patient.last_name.asc())).scalars().all()
