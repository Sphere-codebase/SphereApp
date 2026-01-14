import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Frontend Log")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=False,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_frontend_log_reset_and_append(db_session: Session, tmp_path, monkeypatch) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    monkeypatch.setattr(settings, "frontend_file_logs", True)
    monkeypatch.setattr(settings, "frontend_log_path", str(tmp_path / "frontend.log"))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        reset = client.post(
            "/api/frontend-log/reset",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert reset.status_code == 204

        payload = {"event": "render", "count": 2}
        append = client.post(
            "/api/frontend-log",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert append.status_code == 204

        path = Path(settings.frontend_log_path)
        contents = path.read_text()
        assert json.loads(contents.strip()) == payload
    finally:
        app.dependency_overrides.clear()


def test_frontend_log_rejects_secrets(db_session: Session, tmp_path, monkeypatch) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    monkeypatch.setattr(settings, "frontend_file_logs", True)
    monkeypatch.setattr(settings, "frontend_log_path", str(tmp_path / "frontend.log"))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/frontend-log",
            json={"access_token": "secret"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

        response = client.post(
            "/api/frontend-log",
            json={"message": "Authorization: Bearer abc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_frontend_log_rate_limit(db_session: Session, tmp_path, monkeypatch) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))

    monkeypatch.setattr(settings, "frontend_file_logs", True)
    monkeypatch.setattr(settings, "frontend_log_path", str(tmp_path / "frontend.log"))
    monkeypatch.setattr(settings, "frontend_log_rate_per_sec", 1)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        first = client.post(
            "/api/frontend-log",
            json={"event": "one"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 204

        second = client.post(
            "/api/frontend-log",
            json={"event": "two"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 429
    finally:
        app.dependency_overrides.clear()
