import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app


class FakeLLMClient:
    def __init__(self, response: ChatCompletionResult) -> None:
        self.response = response
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        self.calls += 1
        return self.response


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Max Steps")
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


def test_chat_max_steps_reached(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    fake_llm = FakeLLMClient(
        ChatCompletionResult(
            assistant_text="",
            tool_calls=[ToolCall(id="call-1", name="get_claim", arguments={"claim_id": "bad"})],
        )
    )

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    original_steps = settings.llm_max_steps
    settings.llm_max_steps = 1

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Loop"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assistant_message"] == "Reached max tool steps without resolution."
    finally:
        settings.llm_max_steps = original_steps
        app.dependency_overrides.clear()
