from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.core.tenancy import (
    apply_rls_context,
    reset_current_clinic_id,
    reset_current_is_platform_admin,
    set_current_clinic_id,
    set_current_is_platform_admin,
)
from app.db.id_utils import next_id
from app.db.models import Clinic, InsuranceCompany, Role, User, UserRole, Patient
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow
import sqlalchemy as sa


def _seed_clinic(db_session: Session, name: str, *, is_blocked: bool = False) -> Clinic:
    clinic = Clinic(
        id=next_id(db_session, Clinic),
        name=name,
        created_at=utcnow(),
        is_blocked=is_blocked,
    )
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


def test_blocked_clinic_denied_access(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Blocked Clinic", is_blocked=True)
    doctor = _seed_doctor(db_session, "blocked@example.com", clinic.id)
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token = create_access_token(str(doctor.id))
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 403
        payload = me.json()
        assert payload["error"]["code"] == "CLINIC_BLOCKED"

        patients = client.get("/api/patients", headers={"Authorization": f"Bearer {token}"})
        assert patients.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_platform_admin_access_not_blocked(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Platform Clinic", is_blocked=True)
    admin_role = db_session.execute(
        select(Role).where(Role.code == "platform_staff_admin")
    ).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(
            id=next_id(db_session, Role), code="platform_staff_admin", description="Platform Admin"
        )
        db_session.add(admin_role)
        db_session.flush()
    admin = User(
        id=next_id(db_session, User),
        email="platform@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic.id,
        role="platform_staff_admin",
        created_at=utcnow(),
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token = create_access_token(str(admin.id))
        clinics = client.get("/api/platform/clinics", headers={"Authorization": f"Bearer {token}"})
        assert clinics.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_rls_blocks_cross_clinic_reads(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")
    doctor = _seed_doctor(db_session, "doctor-rls@example.com", clinic_a.id)
    patient = Patient(
        id=next_id(db_session, Patient),
        clinic_id=clinic_a.id,
        doctor_id=doctor.id,
        first_name="Patient",
        last_name="A",
        created_at=utcnow(),
    )
    db_session.add(patient)
    db_session.commit()
    token_admin = set_current_is_platform_admin(False)
    token_clinic = set_current_clinic_id(clinic_b.id)
    try:
        apply_rls_context(db_session, clinic_b.id, False)
        rows = (
            db_session.execute(sa.select(Patient).where(Patient.id == patient.id)).scalars().all()
        )
        assert rows == []
    finally:
        reset_current_clinic_id(token_clinic)
        reset_current_is_platform_admin(token_admin)
