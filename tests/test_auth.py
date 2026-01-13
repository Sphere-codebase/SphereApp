import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Auth")
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
        assert payload["id"] == str(user.id)
        assert payload["tenant_id"] == str(user.tenant_id)
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
