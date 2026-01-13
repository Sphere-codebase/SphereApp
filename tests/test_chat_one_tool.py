import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import ChatMessage, Claim, Patient, Tenant, User
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
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Tools")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        full_name="Jane Doe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        patient_id=patient.id,
        status="open",
        description="Test",
    )
    db_session.add_all([tenant, user, patient, claim])
    db_session.commit()
    return user, claim


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Time")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor-time@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_chat_one_tool_call(db_session: Session) -> None:
    user, claim = _seed_claim(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="get_claim",
                    arguments={"claim_id": str(claim.id)},
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Claim details", tool_calls=[]),
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
            json={"message": "Check claim", "claim_id": str(claim.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Claim details"

        tool_messages = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.tool_name == "get_claim",
                    ChatMessage.tool_result.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        assert tool_messages
    finally:
        app.dependency_overrides.clear()


def test_chat_time_now_tool_call(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="time_now",
                    arguments={"tz": "Asia/Tbilisi"},
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Current time provided", tool_calls=[]),
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
            json={"message": "What time is it?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Current time provided"

        tool_messages = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.tool_name == "time_now",
                    ChatMessage.tool_result.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        assert tool_messages
    finally:
        app.dependency_overrides.clear()
