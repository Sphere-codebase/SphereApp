from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import ChatMessage, ChatSession, Role, User, UserRole
from app.db.session import get_db
from app.llm.client import ChatCompletionResult
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


def _seed_user(db_session: Session) -> User:
    doctor_role = db_session.execute(
        select(Role).where(Role.code == "doctor")
    ).scalar_one_or_none()
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
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def test_chat_no_tools(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    fake_llm = FakeLLMClient([ChatCompletionResult("Hello", [])])

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
            json={"message": "Hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Hello"

        session = db_session.execute(select(ChatSession)).scalar_one()
        messages = (
            db_session.execute(select(ChatMessage).where(ChatMessage.session_id == session.id))
            .scalars()
            .all()
        )
        assert any(message.role == "user" for message in messages)
        assert any(message.role == "assistant" for message in messages)
    finally:
        app.dependency_overrides.clear()
