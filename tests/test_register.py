from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def test_public_register_endpoint_removed() -> None:
    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "x@example.com", "password": "x"})

    assert response.status_code == 404


def test_admin_create_user_requires_admin_token(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/admin/users",
            json={"email": "newdoctor@example.com", "password": "secret"},
        )
        assert response.status_code == 403
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()


def test_admin_create_user_success(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_api_key", "admin-secret")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/admin/users",
            json={"email": "newdoctor@example.com", "password": "secret"},
            headers={"X-Admin-Token": "admin-secret"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["access_token"]
        assert payload["email"] == "newdoctor@example.com"
        assert "doctor" in payload["roles"]

        me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert me.status_code == 200
        me_payload = me.json()
        assert me_payload["email"] == payload["email"]
        assert "doctor" in me_payload["roles"]
    finally:
        app.dependency_overrides.clear()


def test_normal_user_cannot_create_others(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_api_key", "admin-secret")
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
    db_session.add_all([user, UserRole(user_id=user.id, role_id=doctor_role.id)])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/admin/users",
            json={"email": "other@example.com", "password": "secret"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()
