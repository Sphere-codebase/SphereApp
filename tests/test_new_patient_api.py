from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Address,
    Clinic,
    InsuranceCard,
    InsuranceCompany,
    Patient,
    PatientInsurancePolicy,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_doctor(db_session: Session, email: str, clinic_id: int | None = None) -> User:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic_id or 1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def _seed_company(db_session: Session, name: str) -> InsuranceCompany:
    company = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany), name=name, created_at=utcnow()
    )
    db_session.add(company)
    db_session.commit()
    return company


def _override_db(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


def test_create_patient_requires_auth(db_session: Session) -> None:
    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/patients",
            json={"patient_name": "Jane Doe"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_create_patient_creates_patient_address_and_policies(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    doctor = _seed_doctor(db_session, "doctor@example.com", clinic_id=clinic.id)
    company_one = _seed_company(db_session, "Aetna")
    company_two = _seed_company(db_session, "Cigna")

    token = create_access_token(str(doctor.id))
    payload = {
        "patient_name": "John Smith",
        "chart_number": "CH-100",
        "provider_name": "Dr. House",
        "gender": "male",
        "phones": {"primary": "555-1000", "secondary": "555-2000"},
        "address": {
            "line1": "123 Main St",
            "line2": "Apt 4",
            "city": "Boston",
            "state": "MA",
            "zip": "02110",
            "country": "US",
        },
        "insurances": [
            {
                "priority": "primary",
                "insurance_company_id": company_one.id,
                "member_id": "MEM-1",
                "policy_type": "PPO",
                "copay_amount": 20.0,
                "deductible_amount": 100.0,
                "currency": "USD",
                "card": {
                    "storage_key": "cards/primary-front.png",
                    "side": "front",
                    "content_type": "image/png",
                    "size_bytes": 1024,
                },
            },
            {
                "priority": "secondary",
                "insurance_company_id": company_two.id,
                "member_id": "MEM-2",
                "policy_type": "HMO",
                "copay_amount": 15.0,
                "deductible_amount": 75.0,
                "currency": "USD",
            },
        ],
    }

    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/patients",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        created = response.json()
        patient_id = created["id"]

        patient = db_session.get(Patient, patient_id)
        assert patient is not None
        assert patient.chart_number == "CH-100"
        assert patient.provider_name == "Dr. House"
        assert patient.clinic_id == clinic.id

        assert patient.address_id is not None
        address = db_session.get(Address, patient.address_id)
        assert address is not None
        assert address.city == "Boston"

        policies = (
            db_session.execute(
                select(PatientInsurancePolicy).where(
                    PatientInsurancePolicy.patient_id == patient_id
                )
            )
            .scalars()
            .all()
        )
        assert len(policies) == 2
        by_priority = {policy.priority: policy for policy in policies}
        assert by_priority["primary"].insurance_company_id == company_one.id
        assert by_priority["secondary"].insurance_company_id == company_two.id

        cards = (
            db_session.execute(
                select(InsuranceCard).where(InsuranceCard.policy_id == by_priority["primary"].id)
            )
            .scalars()
            .all()
        )
        assert len(cards) == 1
        assert cards[0].storage_key == "cards/primary-front.png"
    finally:
        app.dependency_overrides.clear()


def test_create_patient_enforces_unique_priority(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    doctor = _seed_doctor(db_session, "doctor@example.com", clinic_id=clinic.id)
    company = _seed_company(db_session, "Aetna")
    token = create_access_token(str(doctor.id))

    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/patients",
            json={
                "patient_name": "John Smith",
                "insurances": [
                    {"priority": "primary", "insurance_company_id": company.id},
                    {"priority": "primary", "insurance_company_id": company.id},
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_patient_tenant_isolation(db_session: Session) -> None:
    clinic_one = _seed_clinic(db_session, "Clinic One")
    _seed_clinic(db_session, "Clinic Two")
    doctor = _seed_doctor(db_session, "doctor@example.com", clinic_id=clinic_one.id)
    token = create_access_token(str(doctor.id))

    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/patients",
            json={"patient_name": "Alice Doe"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        patient = db_session.get(Patient, response.json()["id"])
        assert patient is not None
        assert patient.clinic_id == clinic_one.id
    finally:
        app.dependency_overrides.clear()


def test_insurance_companies_list_search(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    doctor = _seed_doctor(db_session, "doctor@example.com", clinic_id=clinic.id)
    _seed_company(db_session, "Aetna")
    _seed_company(db_session, "Blue Cross")
    token = create_access_token(str(doctor.id))

    _override_db(db_session)
    client = TestClient(app)
    try:
        response = client.get(
            "/api/insurance-companies",
            params={"q": "aet", "limit": 20, "offset": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["name"] == "Aetna"
    finally:
        app.dependency_overrides.clear()
