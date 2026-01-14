import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant UI")
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


def test_login_page_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/login")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_chat_page_redirects_when_unauthenticated() -> None:
    client = TestClient(app)
    response = client.get("/app/chat", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers.get("location") == "/login"


def test_chat_page_returns_200_when_authenticated(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("access_token", token)
    try:
        response = client.get("/app/chat")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "logout-button" in response.text
    finally:
        app.dependency_overrides.clear()


def test_admin_users_page_requires_admin(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("access_token", token)
    try:
        response = client.get("/app/admin/users")
        assert response.status_code == 403
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()


def test_admin_users_page_returns_200_for_admin(db_session: Session) -> None:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Admin UI")
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([tenant, admin])
    db_session.commit()
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.cookies.set("access_token", token)
    try:
        response = client.get("/app/admin/users")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "admin-user-form" in response.text
    finally:
        app.dependency_overrides.clear()
