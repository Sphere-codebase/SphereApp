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


def _seed_claim(db_session: Session, doctor: User, patient: Patient, company: InsuranceCompany) -> Claim:
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


def _seed_claim_matrix(db_session: Session):
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")

    doctor_a = _seed_user(db_session, "doctor-a@example.com", "doctor", clinic_a.id)
    doctor_b = _seed_user(db_session, "doctor-b@example.com", "doctor", clinic_a.id)
    chief = _seed_user(db_session, "chief@example.com", "chief_doctor", clinic_a.id)
    clinic_admin = _seed_user(db_session, "admin@example.com", "clinic_admin", clinic_a.id)
    platform_admin = _seed_user(
        db_session, "platform@example.com", "platform_staff_admin", clinic_a.id
    )
    doctor_c = _seed_user(db_session, "doctor-c@example.com", "doctor", clinic_b.id)

    company = _seed_company(db_session, "Company A")
    patient_a = _seed_patient(db_session, doctor_a, "Alice Smith")
    patient_b = _seed_patient(db_session, doctor_b, "Bob Brown")
    patient_c = _seed_patient(db_session, doctor_c, "Clara Jones")

    claim_a = _seed_claim(db_session, doctor_a, patient_a, company)
    claim_b = _seed_claim(db_session, doctor_b, patient_b, company)
    claim_c = _seed_claim(db_session, doctor_c, patient_c, company)

    db_session.commit()
    return {
        "clinic_a": clinic_a,
        "clinic_b": clinic_b,
        "doctor_a": doctor_a,
        "doctor_b": doctor_b,
        "chief": chief,
        "clinic_admin": clinic_admin,
        "platform_admin": platform_admin,
        "doctor_c": doctor_c,
        "company": company,
        "patient_a": patient_a,
        "patient_b": patient_b,
        "patient_c": patient_c,
        "claim_a": claim_a,
        "claim_b": claim_b,
        "claim_c": claim_c,
    }


def test_claim_list_role_matrix(db_session: Session) -> None:
    data = _seed_claim_matrix(db_session)
    _override_db(db_session)
    client = TestClient(app)
    try:
        cases = [
            (data["doctor_a"], {data["claim_a"].id}),
            (data["chief"], {data["claim_a"].id, data["claim_b"].id}),
            (data["clinic_admin"], {data["claim_a"].id, data["claim_b"].id}),
            (
                data["platform_admin"],
                {data["claim_a"].id, data["claim_b"].id, data["claim_c"].id},
            ),
        ]
        for user, expected_ids in cases:
            token = create_access_token(str(user.id))
            response = client.get(
                "/api/claims",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            ids = {item["id"] for item in response.json()}
            assert ids == expected_ids
    finally:
        app.dependency_overrides.clear()


def test_claim_detail_role_matrix(db_session: Session) -> None:
    data = _seed_claim_matrix(db_session)
    _override_db(db_session)
    client = TestClient(app)
    try:
        doctor_token = create_access_token(str(data["doctor_a"].id))
        response = client.get(
            f"/api/claims/{data['claim_b'].id}",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert response.status_code == 404

        chief_token = create_access_token(str(data["chief"].id))
        response = client.get(
            f"/api/claims/{data['claim_b'].id}",
            headers={"Authorization": f"Bearer {chief_token}"},
        )
        assert response.status_code == 200

        admin_token = create_access_token(str(data["clinic_admin"].id))
        response = client.get(
            f"/api/claims/{data['claim_b'].id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

        platform_token = create_access_token(str(data["platform_admin"].id))
        response = client.get(
            f"/api/claims/{data['claim_c'].id}",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert response.status_code == 200

        response = client.get(
            f"/api/claims/{data['claim_c'].id}",
            headers={"Authorization": f"Bearer {chief_token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_claim_create_role_matrix(db_session: Session) -> None:
    data = _seed_claim_matrix(db_session)
    _override_db(db_session)
    client = TestClient(app)
    try:
        cases = [
            (data["doctor_a"], data["patient_a"].id),
            (data["chief"], data["patient_b"].id),
            (data["clinic_admin"], data["patient_b"].id),
            (data["platform_admin"], data["patient_c"].id),
        ]
        for user, patient_id in cases:
            token = create_access_token(str(user.id))
            response = client.post(
                "/api/claims",
                json={
                    "insurance_company_id": data["company"].id,
                    "patient_id": patient_id,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 201

        token = create_access_token(str(data["doctor_a"].id))
        response = client.post(
            "/api/claims",
            json={
                "insurance_company_id": data["company"].id,
                "patient_id": data["patient_b"].id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_claim_update_role_matrix(db_session: Session) -> None:
    data = _seed_claim_matrix(db_session)
    _override_db(db_session)
    client = TestClient(app)
    try:
        token = create_access_token(str(data["doctor_a"].id))
        response = client.patch(
            f"/api/claims/{data['claim_a'].id}",
            json={"claim_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        token = create_access_token(str(data["chief"].id))
        response = client.patch(
            f"/api/claims/{data['claim_b'].id}",
            json={"claim_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        token = create_access_token(str(data["clinic_admin"].id))
        response = client.patch(
            f"/api/claims/{data['claim_b'].id}",
            json={"claim_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        token = create_access_token(str(data["platform_admin"].id))
        response = client.patch(
            f"/api/claims/{data['claim_c'].id}",
            json={"claim_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        token = create_access_token(str(data["doctor_a"].id))
        response = client.patch(
            f"/api/claims/{data['claim_b'].id}",
            json={"claim_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_claim_delete_role_matrix(db_session: Session) -> None:
    clinic_a = _seed_clinic(db_session, "Clinic A")
    clinic_b = _seed_clinic(db_session, "Clinic B")

    doctor = _seed_user(db_session, "doctor@example.com", "doctor", clinic_a.id)
    chief = _seed_user(db_session, "chief@example.com", "chief_doctor", clinic_a.id)
    clinic_admin = _seed_user(db_session, "admin@example.com", "clinic_admin", clinic_a.id)
    platform_admin = _seed_user(
        db_session, "platform@example.com", "platform_staff_admin", clinic_a.id
    )
    doctor_b = _seed_user(db_session, "doctor-b@example.com", "doctor", clinic_a.id)
    doctor_c = _seed_user(db_session, "doctor-c@example.com", "doctor", clinic_b.id)

    company = _seed_company(db_session, "Company A")
    patient_a = _seed_patient(db_session, doctor, "Alice Smith")
    patient_b = _seed_patient(db_session, doctor_b, "Bob Brown")
    patient_c = _seed_patient(db_session, doctor_c, "Clara Jones")

    claim_doctor = _seed_claim(db_session, doctor, patient_a, company)
    claim_chief = _seed_claim(db_session, doctor_b, patient_b, company)
    claim_admin = _seed_claim(db_session, doctor_b, patient_b, company)
    claim_platform = _seed_claim(db_session, doctor_c, patient_c, company)

    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        token = create_access_token(str(doctor.id))
        response = client.delete(
            f"/api/claims/{claim_doctor.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        token = create_access_token(str(chief.id))
        response = client.delete(
            f"/api/claims/{claim_chief.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        token = create_access_token(str(clinic_admin.id))
        response = client.delete(
            f"/api/claims/{claim_admin.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        token = create_access_token(str(platform_admin.id))
        response = client.delete(
            f"/api/claims/{claim_platform.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        token = create_access_token(str(doctor.id))
        response = client.delete(
            f"/api/claims/{claim_chief.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
