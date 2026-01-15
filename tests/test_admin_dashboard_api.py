from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimProcedureFact,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_admin(db_session: Session, is_admin: bool) -> User:
    admin_role = db_session.execute(select(Role).where(Role.code == "admin")).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(id=next_id(db_session, Role), code="admin", description="Admin")
        db_session.add(admin_role)
    doctor_role = db_session.execute(
        select(Role).where(Role.code == "doctor")
    ).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
    db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="admin@example.com" if is_admin else "member@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if is_admin:
        db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db_session.commit()
    return user


def _seed_claim_data(db_session: Session, admin: User) -> Claim:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Company A")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=admin.id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=admin.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        service_date=date(2024, 1, 1),
        created_at=utcnow(),
    )
    code = McpCode(code="99213", description="Office Visit")
    diagnosis = DiagnosisCode(code="A00", description="Cholera")
    procedure = ClaimProcedureFact(
        id=next_id(db_session, ClaimProcedureFact),
        claim_id=claim.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        mcp_code=code.code,
        units=1,
        paid_amount=12.0,
        created_at=utcnow(),
    )
    db_session.add_all([company, patient, claim, code, diagnosis, procedure])
    db_session.flush()
    link = ClaimDiagnosisCode(claim_id=claim.id, diagnosis_code=diagnosis.code)
    db_session.add(link)
    db_session.commit()
    return claim


def test_admin_claims_and_patients_readonly(db_session: Session) -> None:
    admin = _seed_admin(db_session, is_admin=True)
    claim = _seed_claim_data(db_session, admin)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        patients_response = client.get(
            "/api/admin/patients",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert patients_response.status_code == 200
        assert patients_response.json()[0]["first_name"] == "Jane"

        claims_response = client.get(
            "/api/admin/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert claims_response.status_code == 200
        claim_items = claims_response.json()
        assert claim_items[0]["id"] == claim.id
        assert claim_items[0]["patient_name"] == "Jane Doe"

        detail_response = client.get(
            f"/api/admin/claims/{claim.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["procedures"][0]["mcp_code"]["code"] == "99213"
        assert detail["diagnoses"][0]["code"] == "A00"
    finally:
        app.dependency_overrides.clear()


def test_admin_claims_require_admin(db_session: Session) -> None:
    user = _seed_admin(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/admin/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()
