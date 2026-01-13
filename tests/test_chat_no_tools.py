import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import ChatMessage, ChatSession, Tenant, User
from app.db.session import get_db
from app.llm.client import ChatCompletionResult
from app.main import app


class FakeLLMClient:
    def __init__(self, responses: list[ChatCompletionResult]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Chat")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    db_session.add_all([tenant, user])
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
