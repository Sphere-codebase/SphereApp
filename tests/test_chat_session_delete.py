from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import ChatMessage, ChatSession, Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


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


def test_delete_session_removes_messages(db_session: Session) -> None:
    user = _seed_user(db_session, "Delete")
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    first_message_id = next_id(db_session, ChatMessage)
    db_session.add_all(
        [
            ChatMessage(
                id=first_message_id,
                session_id=session.id,
                clinic_id=1,
                role="user",
                content="Hello",
                created_at=utcnow(),
            ),
            ChatMessage(
                id=first_message_id + 1,
                session_id=session.id,
                clinic_id=1,
                role="assistant",
                content="Hi",
                created_at=utcnow(),
            ),
        ]
    )
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.delete(
            f"/api/chat/sessions/{session.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204
        assert response.headers.get("X-Request-ID") is not None

        remaining_session = db_session.get(ChatSession, session.id)
        assert remaining_session is None
        remaining_messages = db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session.id)
        ).scalars()
        assert remaining_messages.first() is None
    finally:
        app.dependency_overrides.clear()


def test_delete_session_other_user_404(db_session: Session) -> None:
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

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.delete(
            f"/api/chat/sessions/{session_b.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.headers.get("X-Request-ID") is not None

        still_there = db_session.get(ChatSession, session_b.id)
        assert still_there is not None
    finally:
        app.dependency_overrides.clear()
