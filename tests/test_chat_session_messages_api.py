from datetime import datetime, timedelta

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


def test_messages_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/sessions/1/messages")

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_messages_returns_ordered_with_timestamps(db_session: Session) -> None:
    user = _seed_user(db_session)
    session = ChatSession(
        id=next_id(db_session, ChatSession), doctor_id=user.id, created_at=utcnow()
    )
    db_session.add(session)
    db_session.commit()

    base_time = datetime.utcnow() - timedelta(hours=1)
    first_message_id = next_id(db_session, ChatMessage)
    msg1 = ChatMessage(
        id=first_message_id,
        session_id=session.id,
        role="user",
        content="First",
        created_at=base_time,
    )
    msg2 = ChatMessage(
        id=first_message_id + 1,
        session_id=session.id,
        role="assistant",
        content="Second",
        created_at=base_time + timedelta(minutes=5),
    )
    tool_msg = ChatMessage(
        id=first_message_id + 2,
        session_id=session.id,
        role="tool",
        content="[tool] noop",
        created_at=base_time + timedelta(minutes=10),
    )
    db_session.add_all([msg1, msg2, tool_msg])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/chat/sessions/{session.id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert [item["content"] for item in payload] == ["First", "Second"]
        assert all("created_at" in item for item in payload)
    finally:
        app.dependency_overrides.clear()


def test_messages_other_user_session_404(db_session: Session) -> None:
    user = _seed_user(db_session)
    other = User(
        id=next_id(db_session, User),
        email="other@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(other)
    db_session.flush()
    session = ChatSession(id=next_id(db_session, ChatSession), doctor_id=other.id)
    db_session.add(session)
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/chat/sessions/{session.id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()


def test_messages_after_chat_includes_new_message(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    class FakeLLMClient:
        def __init__(self) -> None:
            self.response = ChatCompletionResult("OK", [])

        def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
            return self.response

    def override_get_db():
        yield db_session

    def override_llm_client():
        return FakeLLMClient()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        chat = client.post(
            "/chat",
            json={"message": "Hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert chat.status_code == 200
        session_id = chat.json()["session_id"]

        response = client.get(
            f"/api/chat/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert any(item["content"] == "Hello" for item in payload)
        assert all("created_at" in item for item in payload)
    finally:
        app.dependency_overrides.clear()
