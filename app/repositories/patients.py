"""Patient repository helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Address, InsuranceCard, InsuranceCompany, Patient, PatientInsurancePolicy
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


class PatientRepository:
    @staticmethod
    def chart_number_exists(db: Session, *, clinic_id: int, chart_number: str) -> bool:
        existing = db.execute(
            select(Patient.id).where(
                Patient.clinic_id == clinic_id,
                Patient.chart_number == chart_number,
            )
        ).scalar_one_or_none()
        return existing is not None

    @staticmethod
    def create_address(
        db: Session,
        *,
        line1: str,
        line2: str | None,
        city: str,
        state: str | None,
        zip_code: str | None,
        country: str | None,
    ) -> Address:
        address = Address(
            id=next_id(db, Address),
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            zip=zip_code,
            country=country,
            created_at=utcnow(),
        )
        db.add(address)
        db.flush()
        return address

    @staticmethod
    def create_patient(
        db: Session,
        *,
        doctor_id: int,
        clinic_id: int,
        first_name: str | None,
        last_name: str | None,
        chart_number: str | None,
        provider_name: str | None,
        gender: str | None,
        primary_phone: str | None,
        secondary_phone: str | None,
        address_id: int | None,
    ) -> Patient:
        patient = Patient(
            id=next_id(db, Patient),
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            first_name=first_name,
            last_name=last_name,
            chart_number=chart_number,
            provider_name=provider_name,
            gender=gender,
            primary_phone=primary_phone,
            secondary_phone=secondary_phone,
            address_id=address_id,
            created_at=utcnow(),
        )
        db.add(patient)
        db.flush()
        return patient

    @staticmethod
    def create_patient_insurance_policy(
        db: Session,
        *,
        clinic_id: int,
        patient_id: int,
        insurance_company_id: int,
        priority: str,
        member_id: str | None,
        policy_type: str | None,
        copay_amount: float | None,
        deductible_amount: float | None,
        currency: str | None,
    ) -> PatientInsurancePolicy:
        policy = PatientInsurancePolicy(
            id=next_id(db, PatientInsurancePolicy),
            clinic_id=clinic_id,
            patient_id=patient_id,
            insurance_company_id=insurance_company_id,
            priority=priority,
            member_id=member_id,
            policy_type=policy_type,
            copay_amount=copay_amount,
            deductible_amount=deductible_amount,
            currency=currency,
            created_at=utcnow(),
        )
        db.add(policy)
        db.flush()
        return policy

    @staticmethod
    def create_insurance_card(
        db: Session,
        *,
        policy_id: int,
        side: str,
        storage_key: str,
        content_type: str | None,
        size_bytes: int | None,
    ) -> InsuranceCard:
        card = InsuranceCard(
            id=next_id(db, InsuranceCard),
            policy_id=policy_id,
            side=side,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_at=utcnow(),
        )
        db.add(card)
        db.flush()
        return card


class InsuranceCompanyRepository:
    @staticmethod
    def list_for_dropdown(
        db: Session,
        *,
        q: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[InsuranceCompany], int]:
        base_stmt = select(InsuranceCompany)
        if q:
            like = f"%{q}%"
            base_stmt = base_stmt.where(InsuranceCompany.name.ilike(like))

        total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()
        items = (
            db.execute(base_stmt.order_by(InsuranceCompany.name.asc()).limit(limit).offset(offset))
            .scalars()
            .all()
        )
        return items, int(total or 0)

    @staticmethod
    def ensure_ids_exist(
        db: Session,
        *,
        company_ids: list[int],
    ) -> set[int]:
        rows = (
            db.execute(select(InsuranceCompany.id).where(InsuranceCompany.id.in_(company_ids)))
            .scalars()
            .all()
        )
        return set(rows)
