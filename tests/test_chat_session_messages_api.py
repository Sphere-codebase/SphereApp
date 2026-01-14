import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.models import ChatMessage, ChatSession, Tenant, User
from app.db.session import get_db
from app.llm.client import ChatCompletionResult
from app.main import app


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Messages")
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


def test_messages_requires_auth() -> None:
    client = TestClient(app)
    response = client.get(f"/api/chat/sessions/{uuid.uuid4()}/messages")

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_messages_returns_ordered_with_timestamps(db_session: Session) -> None:
    user = _seed_user(db_session)
    session = ChatSession(id=uuid.uuid4(), tenant_id=user.tenant_id, user_id=user.id)
    db_session.add(session)
    db_session.commit()

    base_time = datetime.now(tz=UTC) - timedelta(hours=1)
    msg1 = ChatMessage(
        tenant_id=user.tenant_id,
        session_id=session.id,
        role="user",
        content="First",
        created_at=base_time,
    )
    msg2 = ChatMessage(
        tenant_id=user.tenant_id,
        session_id=session.id,
        role="assistant",
        content="Second",
        created_at=base_time + timedelta(minutes=5),
    )
    tool_msg = ChatMessage(
        tenant_id=user.tenant_id,
        session_id=session.id,
        role="tool",
        content=None,
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


def test_messages_cross_tenant_session_404(db_session: Session) -> None:
    user = _seed_user(db_session)
    other_tenant = Tenant(id=uuid.uuid4(), name="Tenant Other")
    other_user = User(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        email="other@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    other_session = ChatSession(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        user_id=other_user.id,
    )
    db_session.add_all([other_tenant, other_user, other_session])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/chat/sessions/{other_session.id}/messages",
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
