from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
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


def _seed_user(db_session: Session) -> User:
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
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
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
