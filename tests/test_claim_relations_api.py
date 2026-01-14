import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Claim, ClaimStatus, Patient, Tenant, User, Visit
from app.db.session import get_db
from app.main import app


def _seed_claim_with_patients(db_session: Session) -> tuple[User, Claim, Patient, Patient]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Claims Relations")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    patient_a = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
    )
    patient_b = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="John",
        last_name="Smith",
        full_name="John Smith",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        patient_id=patient_a.id,
        status=ClaimStatus.DRAFT,
    )
    db_session.add_all([tenant, user, patient_a, patient_b, claim])
    db_session.commit()
    return user, claim, patient_a, patient_b


def test_attach_visit_other_patient_returns_422(db_session: Session) -> None:
    user, claim, _patient_a, patient_b = _seed_claim_with_patients(db_session)
    visit = Visit(
        id=uuid.uuid4(),
        tenant_id=claim.tenant_id,
        patient_id=patient_b.id,
        visited_at=datetime.now(tz=UTC),
    )
    db_session.add(visit)
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/claims/{claim.id}/visits",
            json={"visit_ids": [str(visit.id)]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "HTTP_422"
    finally:
        app.dependency_overrides.clear()


def test_add_procedure_missing_code_returns_404(db_session: Session) -> None:
    user, claim, _patient_a, _patient_b = _seed_claim_with_patients(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/claims/{claim.id}/procedures",
            json={"procedures": [{"procedure_code_id": str(uuid.uuid4()), "units": 1}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "HTTP_404"
    finally:
        app.dependency_overrides.clear()
