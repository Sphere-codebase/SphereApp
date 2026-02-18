import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import Claim, Clinic, InsuranceCompany, Patient, User
from app.llm.tools import execute_tool
from app.llm.tools.registry import ToolContext
from app.utils.time import utcnow


def _seed_clinic(db_session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session, email: str, role: str, clinic_id: int) -> User:
    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic_id,
        role=role,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _seed_company(db_session, name: str) -> InsuranceCompany:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name=name)
    db_session.add(company)
    db_session.flush()
    return company


def _seed_patient(db_session, doctor: User, name: str) -> Patient:
    first, last = name.split()
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=doctor.id,
        clinic_id=doctor.clinic_id,
        first_name=first,
        last_name=last,
        created_at=utcnow(),
    )
    db_session.add(patient)
    db_session.flush()
    return patient


def _seed_claim(db_session, doctor: User, patient: Patient, company: InsuranceCompany) -> Claim:
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=doctor.id,
        clinic_id=doctor.clinic_id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add(claim)
    db_session.flush()
    return claim


def test_tool_update_claim_requires_confirm(db_session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    doctor = _seed_user(db_session, "doctor@example.com", "doctor", clinic.id)
    company = _seed_company(db_session, "Company A")
    patient = _seed_patient(db_session, doctor, "Alice Smith")
    claim = _seed_claim(db_session, doctor, patient, company)
    db_session.commit()

    ctx = ToolContext(
        db=db_session,
        user_id=doctor.id,
        clinic_id=doctor.clinic_id,
        role=doctor.role,
    )

    result = execute_tool(
        "update_claim_fields",
        {"claim_id": claim.id, "patch": {"claim_status": "SUBMITTED"}},
        ctx,
    )
    assert result.get("action_required") is True
    db_session.refresh(claim)
    assert claim.claim_status == "DRAFT"

    result = execute_tool(
        "update_claim_fields",
        {
            "claim_id": claim.id,
            "patch": {"claim_status": "SUBMITTED"},
            "confirm": True,
        },
        ctx,
    )
    assert result.get("updated") is True
    db_session.refresh(claim)
    assert claim.claim_status == "SUBMITTED"


def test_tool_update_claim_cross_clinic_404(db_session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    doctor_a = _seed_user(db_session, "doctor-a@example.com", "doctor", clinic_a.id)
    doctor_b = _seed_user(db_session, "doctor-b@example.com", "doctor", clinic_b.id)
    company = _seed_company(db_session, "Company A")
    patient = _seed_patient(db_session, doctor_a, "Alice Smith")
    claim = _seed_claim(db_session, doctor_a, patient, company)
    db_session.commit()

    ctx = ToolContext(
        db=db_session,
        user_id=doctor_b.id,
        clinic_id=doctor_b.clinic_id,
        role=doctor_b.role,
    )

    with pytest.raises(HTTPException) as exc:
        execute_tool(
            "update_claim_fields",
            {
                "claim_id": claim.id,
                "patch": {"claim_status": "SUBMITTED"},
                "confirm": True,
            },
            ctx,
        )

    assert exc.value.status_code == 404
    db_session.refresh(claim)
    assert claim.claim_status == "DRAFT"
