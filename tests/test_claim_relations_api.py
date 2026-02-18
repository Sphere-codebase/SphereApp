from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Clinic, InsuranceCompany, Patient, Role, User, UserRole
from app.db.models.claim import Claim
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session: Session, email: str, clinic_id: int = 1) -> User:
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


def _seed_claim(db_session: Session, user: User) -> Claim:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Company A")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        clinic_id=user.clinic_id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all([company, patient, claim])
    db_session.commit()
    return claim


def test_add_mcp_code_missing_returns_404(db_session: Session) -> None:
    user = _seed_user(db_session, "doctor@example.com")
    claim = _seed_claim(db_session, user)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/claims/{claim.id}/mcp-codes",
            json={"mcp_codes": ["99999"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "HTTP_404"
    finally:
        app.dependency_overrides.clear()


def test_claim_access_restricted_to_owner(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    other_clinic = _seed_clinic(db_session, "Clinic B")
    owner = _seed_user(db_session, "owner@example.com", clinic_id=clinic.id)
    other = _seed_user(db_session, "other@example.com", clinic_id=other_clinic.id)
    claim = _seed_claim(db_session, owner)
    token = create_access_token(str(other.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/claims/{claim.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
