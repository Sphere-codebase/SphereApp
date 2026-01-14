import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
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


def _seed_secondary_user(db_session: Session, tenant_id: uuid.UUID, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=email,
        full_name="Secondary User",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_non_admin_cannot_list_users(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()


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
                "is_admin": False,
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["email"] == "newuser@example.com"
        assert payload["is_admin"] is False
        assert payload["is_active"] is True

        created = db_session.get(User, uuid.UUID(payload["id"]))
        assert created is not None
        assert created.tenant_id == admin.tenant_id
        assert created.full_name == "New User"
        assert created.is_admin is False
    finally:
        app.dependency_overrides.clear()


def test_admin_update_user_success(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    target = _seed_secondary_user(db_session, admin.tenant_id, "target@example.com")
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/admin/users/{target.id}",
            json={"full_name": "Updated Name", "is_active": False, "is_admin": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["full_name"] == "Updated Name"
        assert payload["is_active"] is False
        assert payload["is_admin"] is True
    finally:
        app.dependency_overrides.clear()


def test_admin_update_email_conflict_returns_409(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    user_a = _seed_secondary_user(db_session, admin.tenant_id, "a@example.com")
    user_b = _seed_secondary_user(db_session, admin.tenant_id, "b@example.com")
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/admin/users/{user_b.id}",
            json={"email": user_a.email},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "USER_EMAIL_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_admin_self_demote_blocked_when_last_admin(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/admin/users/{admin.id}",
            json={"is_admin": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LAST_ADMIN"
    finally:
        app.dependency_overrides.clear()


def test_admin_reset_password_updates_hash(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    target = _seed_secondary_user(db_session, admin.tenant_id, "reset@example.com")
    old_hash = target.hashed_password
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/admin/users/{target.id}/reset-password",
            json={"password": "newsecret"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204
        db_session.refresh(target)
        assert target.hashed_password != old_hash
        assert verify_password("newsecret", target.hashed_password) is True
    finally:
        app.dependency_overrides.clear()


def test_admin_user_tenant_isolation(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    other_user = _seed_user(db_session)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/admin/users/{other_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
