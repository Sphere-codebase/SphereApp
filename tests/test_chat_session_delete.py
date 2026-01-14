import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import ChatMessage, ChatSession, Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session, name: str) -> User:
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {name}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"doctor-{name.lower()}@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_delete_session_removes_messages(db_session: Session) -> None:
    user = _seed_user(db_session, "Delete")
    session = ChatSession(tenant_id=user.tenant_id, user_id=user.id)
    db_session.add(session)
    db_session.flush()
    db_session.add_all(
        [
            ChatMessage(
                tenant_id=user.tenant_id,
                session_id=session.id,
                role="user",
                content="Hello",
            ),
            ChatMessage(
                tenant_id=user.tenant_id,
                session_id=session.id,
                role="assistant",
                content="Hi",
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


def test_delete_session_cross_tenant_404(db_session: Session) -> None:
    user_a = _seed_user(db_session, "A")
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant B")
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="doctor-b@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    session_b = ChatSession(tenant_id=tenant_b.id, user_id=user_b.id)
    db_session.add_all([tenant_b, user_b, session_b])
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
