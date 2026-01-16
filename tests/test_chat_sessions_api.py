from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import ChatSession, Role, User, UserRole
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
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def test_list_sessions_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/sessions")

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_list_sessions_scoped_to_user(db_session: Session) -> None:
    user_a = _seed_user(db_session, "A")
    user_b = _seed_user(db_session, "B")

    first_session_id = next_id(db_session, ChatSession)
    session_a1 = ChatSession(
        id=first_session_id,
        doctor_id=user_a.id,
        created_at=utcnow(),
    )
    session_a2 = ChatSession(
        id=first_session_id + 1,
        doctor_id=user_a.id,
        created_at=utcnow(),
    )
    session_b = ChatSession(
        id=first_session_id + 2,
        doctor_id=user_b.id,
        created_at=utcnow(),
    )
    db_session.add_all([session_a1, session_a2, session_b])
    db_session.commit()

    token = create_access_token(str(user_a.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/chat/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        returned_ids = {item["id"] for item in payload}
        assert returned_ids == {session_a1.id, session_a2.id}
    finally:
        app.dependency_overrides.clear()


def test_create_session_requires_auth() -> None:
    client = TestClient(app)
    response = client.post("/api/chat/sessions", json={})

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_create_session_success(db_session: Session) -> None:
    user = _seed_user(db_session, "Create")
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/chat/sessions",
            json={"title": "My session"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["title"] == "My session"

        created = db_session.get(ChatSession, int(payload["id"]))
        assert created is not None
        assert created.doctor_id == user.id
    finally:
        app.dependency_overrides.clear()


def test_get_session_returns_200(db_session: Session) -> None:
    user = _seed_user(db_session, "Get")
    session = ChatSession(
        id=next_id(db_session, ChatSession),
        doctor_id=user.id,
        created_at=utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/chat/sessions/{session.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == session.id
    finally:
        app.dependency_overrides.clear()
