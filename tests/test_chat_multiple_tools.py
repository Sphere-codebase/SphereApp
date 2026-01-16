from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    ChatMessage,
    Claim,
    InsuranceCompany,
    Patient,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app
from app.utils.time import utcnow


class FakeLLMClient:
    def __init__(self, responses: list[ChatCompletionResult]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _seed_claim(db_session: Session) -> tuple[User, Claim]:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Company A")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all(
        [user, UserRole(user_id=user.id, role_id=doctor_role.id), company, patient, claim]
    )
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
                    arguments={"claim_id": claim.id},
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
                    ChatMessage.session_id == int(session_id),
                    ChatMessage.content.ilike("%[tool_result]%"),
                )
            )
            .scalars()
            .all()
        )
        assert len(tool_messages) == 2
        assert any("get_claim" in item.content for item in tool_messages)
        assert any("time_now" in item.content for item in tool_messages)
    finally:
        app.dependency_overrides.clear()
