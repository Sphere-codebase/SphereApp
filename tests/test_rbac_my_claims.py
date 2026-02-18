import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Claim, Clinic, InsuranceCompany, Patient, User
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session: Session, email: str, role: str, clinic_id: int) -> User:
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


def _seed_company(db_session: Session, name: str) -> InsuranceCompany:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name=name)
    db_session.add(company)
    db_session.flush()
    return company


def _seed_patient(db_session: Session, doctor: User, name: str) -> Patient:
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


def _seed_claim(
    db_session: Session, doctor: User, patient: Patient, company: InsuranceCompany
) -> Claim:
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


def _override_db(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.parametrize(
    "role",
    ["doctor", "chief_doctor", "clinic_admin", "platform_staff_admin"],
)
def test_my_claims_scoped_to_user_across_roles(db_session: Session, role: str) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    user = _seed_user(db_session, f"{role}@example.com", role, clinic.id)
    other = _seed_user(db_session, "other@example.com", "doctor", clinic.id)
    company = _seed_company(db_session, "Company A")

    patient_user = _seed_patient(db_session, user, "Alice Smith")
    patient_other = _seed_patient(db_session, other, "Bob Brown")

    claim_user = _seed_claim(db_session, user, patient_user, company)
    _seed_claim(db_session, other, patient_other, company)

    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token = create_access_token(str(user.id))
        response = client.get(
            "/api/claims/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert [item["id"] for item in payload["items"]] == [claim_user.id]
    finally:
        app.dependency_overrides.clear()
