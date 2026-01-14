import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_admin(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Admin")
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([tenant, admin])
    db_session.commit()
    return admin


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Member")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="member@example.com",
        full_name="Member User",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=False,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_admin_create_user_success(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/admin/users",
            json={
                "email": "newuser@example.com",
                "full_name": "New User",
                "password": "secret",
                "role": "",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["email"] == "newuser@example.com"

        created = db_session.get(User, uuid.UUID(payload["user_id"]))
        assert created is not None
        assert created.tenant_id == admin.tenant_id
        assert created.full_name == "New User"
        assert created.is_admin is False
    finally:
        app.dependency_overrides.clear()


def test_non_admin_cannot_create_user(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/admin/users",
            json={
                "email": "newuser@example.com",
                "full_name": "New User",
                "password": "secret",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()
