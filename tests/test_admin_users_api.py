from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_user(db_session: Session, email: str, is_admin: bool) -> User:
    admin_role = db_session.execute(select(Role).where(Role.code == "admin")).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(id=next_id(db_session, Role), code="admin", description="Admin")
        db_session.add(admin_role)
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
    db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email=email,
        full_name="User",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if is_admin:
        db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db_session.commit()
    return user


def test_non_admin_cannot_list_users(db_session: Session) -> None:
    user = _seed_user(db_session, "member@example.com", is_admin=False)
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
    admin = _seed_user(db_session, "admin@example.com", is_admin=True)
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
                "roles": ["doctor"],
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["email"] == "newuser@example.com"
        assert payload["is_active"] is True
        assert "doctor" in payload["roles"]

        created = db_session.get(User, int(payload["id"]))
        assert created is not None
        assert created.full_name == "New User"
    finally:
        app.dependency_overrides.clear()


def test_admin_update_user_success(db_session: Session) -> None:
    admin = _seed_user(db_session, "admin@example.com", is_admin=True)
    target = _seed_user(db_session, "target@example.com", is_admin=False)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/admin/users/{target.id}",
            json={"full_name": "Updated Name", "roles": ["admin", "doctor"], "is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["full_name"] == "Updated Name"
        assert payload["is_active"] is False
        assert "admin" in payload["roles"]
    finally:
        app.dependency_overrides.clear()


def test_admin_update_email_conflict_returns_409(db_session: Session) -> None:
    admin = _seed_user(db_session, "admin@example.com", is_admin=True)
    user_a = _seed_user(db_session, "a@example.com", is_admin=False)
    user_b = _seed_user(db_session, "b@example.com", is_admin=False)
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
    admin = _seed_user(db_session, "admin@example.com", is_admin=True)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/admin/users/{admin.id}",
            json={"roles": ["doctor"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LAST_ADMIN"
    finally:
        app.dependency_overrides.clear()


def test_admin_reset_password_updates_hash(db_session: Session) -> None:
    admin = _seed_user(db_session, "admin@example.com", is_admin=True)
    target = _seed_user(db_session, "reset@example.com", is_admin=False)
    old_hash = target.password_hash
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
        assert target.password_hash != old_hash
        assert verify_password("newsecret", target.password_hash) is True
    finally:
        app.dependency_overrides.clear()
