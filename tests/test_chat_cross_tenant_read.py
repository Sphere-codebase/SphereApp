import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import Agency, Claim, ClaimStatus, Patient, Tenant, User
from app.db.session import get_db
from app.llm.client import ChatCompletionResult
from app.main import app


class FakeLLMClient:
    def __init__(self, response: ChatCompletionResult) -> None:
        self.response = response

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        return self.response


def test_cross_tenant_claim_read_returns_404(db_session: Session) -> None:
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant A")
    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant B")
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="doctor-b@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    agency_b = Agency(id=uuid.uuid4(), name="Agency B", slug="agency-b", is_active=True)
    patient_b = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        first_name="Jane",
        last_name="Roe",
        full_name="Jane Roe",
    )
    claim_b = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        agency_id=agency_b.id,
        patient_id=patient_b.id,
        status=ClaimStatus.DRAFT,
    )
    db_session.add_all([tenant_a, user_a, tenant_b, user_b, agency_b, patient_b, claim_b])
    db_session.commit()

    token = create_access_token(str(user_a.id))
    fake_llm = FakeLLMClient(ChatCompletionResult("Should not be called", []))

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Get claim", "claim_id": str(claim_b.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
