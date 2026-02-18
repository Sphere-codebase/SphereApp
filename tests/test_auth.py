from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_user(db_session: Session) -> User:
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
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def test_auth_flow(db_session: Session) -> None:
    user = _seed_user(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        no_token = client.get("/auth/me")
        assert no_token.status_code == 401

        bad_token = client.get("/auth/me", headers={"Authorization": "Bearer bad"})
        assert bad_token.status_code == 401

        login = client.post(
            "/auth/login",
            json={"email": user.email, "password": "secret"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        payload = me.json()
        assert payload["id"] == user.id
        assert "doctor" in payload["roles"]
    finally:
        app.dependency_overrides.clear()


def test_valid_token_without_login(db_session: Session) -> None:
    user = _seed_user(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        token = create_access_token(str(user.id))
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
    finally:
        app.dependency_overrides.clear()
