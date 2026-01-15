import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import Agency, ChatMessage, Claim, ClaimStatus, Patient, Tenant, User
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
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Multi Tools")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Agency Multi",
        slug="agency-multi",
        is_active=True,
    )
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
        description="Test",
    )
    db_session.add_all([tenant, user, agency, patient, claim])
    db_session.commit()
    return user, claim


def test_chat_multiple_tools_in_one_step(db_session: Session) -> None:
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
                ),
                ToolCall(
                    id="call-2",
                    name="time_now",
                    arguments={"tz": "UTC"},
                ),
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
            json={"message": "Run tools"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Done"
        session_id = payload["session_id"]

        tool_messages = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == uuid.UUID(session_id),
                    ChatMessage.tool_name.in_(["get_claim", "time_now"]),
                    ChatMessage.tool_result.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        assert len(tool_messages) == 2
        results_by_name = {item.tool_name: item.tool_result for item in tool_messages}
        assert results_by_name["get_claim"]["claim"]["id"] == str(claim.id)
        assert results_by_name["time_now"]["tz"] == "UTC"
    finally:
        app.dependency_overrides.clear()
