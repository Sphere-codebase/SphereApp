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
    def __init__(self, response: ChatCompletionResult) -> None:
        self.response = response

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        return self.response


def _seed_user(db_session: Session, name: str) -> User:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()
    user = User(
        id=next_id(db_session, User),
        email=f"doctor-{name.lower()}@example.com",
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


def test_chat_reuses_session(db_session: Session) -> None:
    user = _seed_user(db_session, "Reuse")
    token = create_access_token(str(user.id))
    fake_llm = FakeLLMClient(ChatCompletionResult("OK", []))

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        first = client.post(
            "/chat",
            json={"message": "Hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200
        session_id = first.json()["session_id"]

        sessions = db_session.execute(select(ChatSession).where(ChatSession.doctor_id == user.id))
        session_rows = sessions.scalars().all()
        assert session_rows
        assert len(session_rows) == 1

        second = client.post(
            "/chat",
            json={"message": "Again", "session_id": session_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200
        assert second.json()["session_id"] == session_id

        sessions = db_session.execute(select(ChatSession).where(ChatSession.doctor_id == user.id))
        session_rows = sessions.scalars().all()
        assert len(session_rows) == 1

        messages = db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == int(session_id))
        ).scalars()
        assert len(messages.all()) == 4
    finally:
        app.dependency_overrides.clear()


def test_chat_session_other_user_returns_404(db_session: Session) -> None:
    user_a = _seed_user(db_session, "A")
    user_b = _seed_user(db_session, "B")
    session_b = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user_b.id,
        clinic_id=1,
    )
    db_session.add(session_b)
    db_session.commit()

    token = create_access_token(str(user_a.id))
    fake_llm = FakeLLMClient(ChatCompletionResult("OK", []))

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
            json={"message": "Test", "session_id": str(session_b.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

        sessions = db_session.execute(select(ChatSession).where(ChatSession.doctor_id == user_a.id))
        assert sessions.scalars().first() is None
    finally:
        app.dependency_overrides.clear()
