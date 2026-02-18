from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Clinic, InsuranceCompany, Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_doctor(db_session: Session, email: str, clinic_id: int) -> User:
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
        clinic_id=clinic_id,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def _seed_company(db_session: Session, name: str) -> InsuranceCompany:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name=name)
    db_session.add(company)
    db_session.flush()
    return company


def _override_db(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


def test_cross_clinic_reads_return_404(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    doctor_a = _seed_doctor(db_session, "doctor-a@example.com", clinic_a.id)
    doctor_b = _seed_doctor(db_session, "doctor-b@example.com", clinic_b.id)
    company = _seed_company(db_session, "Company A")
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token_a = create_access_token(str(doctor_a.id))
        token_b = create_access_token(str(doctor_b.id))

        patient_response = client.post(
            "/api/patients",
            json={"patient_name": "Jane Doe"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert patient_response.status_code == 201
        patient_id = patient_response.json()["id"]

        claim_response = client.post(
            "/api/claims",
            json={"insurance_company_id": company.id, "patient_id": patient_id},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert claim_response.status_code == 201
        claim_id = claim_response.json()["id"]

        forbidden_patient = client.get(
            f"/api/patients/{patient_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert forbidden_patient.status_code == 404

        forbidden_claim = client.get(
            f"/api/claims/{claim_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert forbidden_claim.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_list_endpoints_are_clinic_scoped(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    doctor_a = _seed_doctor(db_session, "doctor-a@example.com", clinic_a.id)
    doctor_b = _seed_doctor(db_session, "doctor-b@example.com", clinic_b.id)
    company = _seed_company(db_session, "Company A")
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token_a = create_access_token(str(doctor_a.id))
        token_b = create_access_token(str(doctor_b.id))

        patient_a = client.post(
            "/api/patients",
            json={"patient_name": "Alice Smith"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        patient_b = client.post(
            "/api/patients",
            json={"patient_name": "Bob Brown"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert patient_a.status_code == 201
        assert patient_b.status_code == 201

        claim_a = client.post(
            "/api/claims",
            json={"insurance_company_id": company.id, "patient_id": patient_a.json()["id"]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        claim_b = client.post(
            "/api/claims",
            json={"insurance_company_id": company.id, "patient_id": patient_b.json()["id"]},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert claim_a.status_code == 201
        assert claim_b.status_code == 201

        patient_list = client.get(
            "/api/patients",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert patient_list.status_code == 200
        patient_ids = {item["id"] for item in patient_list.json()}
        assert patient_a.json()["id"] in patient_ids
        assert patient_b.json()["id"] not in patient_ids

        claim_list = client.get(
            "/api/claims",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert claim_list.status_code == 200
        claim_ids = {item["id"] for item in claim_list.json()}
        assert claim_a.json()["id"] in claim_ids
        assert claim_b.json()["id"] not in claim_ids
    finally:
        app.dependency_overrides.clear()
