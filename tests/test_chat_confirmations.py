import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import Agency, Claim, ClaimEvent, ClaimStatus, Patient, Tenant, User
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app


class FakeLLMClient:
    def __init__(self, responses: list[ChatCompletionResult]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _seed_claim(db_session: Session) -> tuple[User, Claim]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Confirm")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    agency = Agency(id=uuid.uuid4(), name="Agency Confirm", slug="agency-confirm", is_active=True)
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        agency_id=agency.id,
        patient_id=patient.id,
        status=ClaimStatus.DRAFT,
        description="Original",
    )
    db_session.add_all([tenant, user, agency, patient, claim])
    db_session.commit()
    return user, claim


def test_update_requires_confirmation(db_session: Session) -> None:
    user, claim = _seed_claim(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Propose update",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={"claim_id": str(claim.id), "patch": {"status": "SUBMITTED"}},
                )
            ],
        )
    ]
    fake_llm = FakeLLMClient(responses)

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
            json={"message": "Close claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["action_required"] is True
        assert payload["proposed_changes"]["patch"]["status"] == "SUBMITTED"

        db_session.refresh(claim)
        assert claim.status == ClaimStatus.DRAFT
        events = db_session.execute(select(ClaimEvent).where(ClaimEvent.claim_id == claim.id))
        assert events.scalars().first() is None
    finally:
        app.dependency_overrides.clear()


def test_update_with_confirmation_writes(db_session: Session) -> None:
    user, claim = _seed_claim(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Update now",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={
                        "claim_id": str(claim.id),
                        "patch": {"status": "SUBMITTED"},
                        "confirm": True,
                    },
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Done", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

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
            json={"message": "Close claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        db_session.refresh(claim)
        assert claim.status == ClaimStatus.SUBMITTED

        event = db_session.execute(select(ClaimEvent).where(ClaimEvent.claim_id == claim.id))
        claim_event = event.scalars().first()
        assert claim_event is not None
        assert claim_event.user_id == user.id
        assert claim_event.chat_session_id is not None
    finally:
        app.dependency_overrides.clear()


def test_cross_tenant_update_returns_404(db_session: Session) -> None:
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
    agency_b = Agency(
        id=uuid.uuid4(),
        name="Agency B",
        slug="agency-b",
        is_active=True,
    )
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
    responses = [
        ChatCompletionResult(
            assistant_text="Update other tenant",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="update_claim_fields",
                    arguments={
                        "claim_id": str(claim_b.id),
                        "patch": {"status": "DENIED"},
                        "confirm": True,
                    },
                )
            ],
        )
    ]
    fake_llm = FakeLLMClient(responses)

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
            json={"message": "Close other tenant claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
