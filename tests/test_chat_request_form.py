import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
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


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Request Form")
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


def test_request_form_returns_ui_action(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Need details",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="request_form",
                    arguments={
                        "fields": [
                            {
                                "name": "date_of_service",
                                "label": "Date of Service",
                                "type": "date",
                                "required": True,
                            }
                        ]
                    },
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Thanks", tool_calls=[]),
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
            json={"message": "Start"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["assistant_message"] == "Thanks"
        assert payload["ui_actions"] == [
            {
                "type": "form",
                "fields": [
                    {
                        "name": "date_of_service",
                        "label": "Date of Service",
                        "type": "date",
                        "required": True,
                    }
                ],
            }
        ]
    finally:
        app.dependency_overrides.clear()
