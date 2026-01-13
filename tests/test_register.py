from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app


def test_register_ok_returns_token_and_me_works(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {"email": "newdoctor@example.com", "password": "secret"}
        response = client.post("/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert me.status_code == 200
        me_payload = me.json()
        assert me_payload["email"] == payload["email"]
        assert "tenant_id" in me_payload
    finally:
        app.dependency_overrides.clear()


def test_register_duplicate_email_409(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {"email": "dupe@example.com", "password": "secret"}
        first = client.post("/auth/register", json=payload)
        assert first.status_code == 201

        second = client.post("/auth/register", json=payload)
        assert second.status_code == 409
        error = second.json()["error"]
        assert error["code"] == "USER_ALREADY_EXISTS"
    finally:
        app.dependency_overrides.clear()
