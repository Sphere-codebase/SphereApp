from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.main import app
from app.utils.time import utcnow


class FakeLLMClient:
    def __init__(self, response: ChatCompletionResult) -> None:
        self.response = response
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        self.calls += 1
        return self.response


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
