import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import (
    Agency,
    Claim,
    ClaimDiagnosis,
    ClaimProcedure,
    ClaimProcedurePayment,
    ClaimStatus,
    Diagnosis,
    Patient,
    ProcedureCode,
    Tenant,
    User,
)
from app.db.session import get_db
from app.main import app


def _seed_admin(db_session: Session, is_admin: bool) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Admin Dashboard")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com" if is_admin else "member@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=is_admin,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def _seed_claim_data(db_session: Session, admin: User) -> Claim:
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        name="Agency A",
        slug="agency-a",
        is_active=True,
    )
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        agency_id=agency.id,
        patient_id=patient.id,
        status=ClaimStatus.DRAFT,
        service_from=datetime(2024, 1, 1, tzinfo=UTC).date(),
    )
    code = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        code="99213",
        title="Office Visit",
    )
    diagnosis = Diagnosis(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        code="A00",
        title="Cholera",
    )
    procedure = ClaimProcedure(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        claim_id=claim.id,
        procedure_code_id=code.id,
        units=1,
        paid_amount_cents=1200,
    )
    payment = ClaimProcedurePayment(
        id=uuid.uuid4(),
        tenant_id=admin.tenant_id,
        claim_procedure_id=procedure.id,
        paid_amount_cents=1200,
        paid_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    link = ClaimDiagnosis(
        tenant_id=admin.tenant_id,
        claim_id=claim.id,
        diagnosis_id=diagnosis.id,
    )
    db_session.add_all(
        [agency, patient, claim, code, diagnosis, procedure, payment, link]
    )
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
        assert patients_response.json()[0]["full_name"] == "Jane Doe"

        claims_response = client.get(
            "/api/admin/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert claims_response.status_code == 200
        claim_items = claims_response.json()
        assert claim_items[0]["id"] == str(claim.id)
        assert claim_items[0]["patient_name"] == "Jane Doe"

        detail_response = client.get(
            f"/api/admin/claims/{claim.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["procedures"][0]["procedure_code"]["code"] == "99213"
        assert detail["procedures"][0]["payments"][0]["paid_amount_cents"] == 1200
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
