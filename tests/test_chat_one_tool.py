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


def _seed_user(db_session: Session, email: str) -> User:
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
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def _seed_claim(db_session: Session) -> tuple[User, Claim]:
    user = _seed_user(db_session, "doctor@example.com")
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Company A")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        clinic_id=1,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        clinic_id=1,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all([company, patient, claim])
    db_session.commit()
    return user, claim


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
                    arguments={"claim_id": claim.id},
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
            json={"message": "Check claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Claim details"

        tool_messages = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.content.ilike("%[tool_result] get_claim%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_messages
    finally:
        app.dependency_overrides.clear()


def test_chat_time_now_tool_call(db_session: Session) -> None:
    user = _seed_user(db_session, "doctor-time@example.com")
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
                    ChatMessage.content.ilike("%[tool_result] time_now%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_messages
    finally:
        app.dependency_overrides.clear()
