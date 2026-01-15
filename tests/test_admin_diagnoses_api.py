import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session, is_admin: bool) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Diagnoses")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com" if is_admin else "member@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=is_admin,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_diagnoses_require_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/admin/diagnoses",
            json={"code": "A00", "title": "Cholera"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()


def test_admin_diagnoses_crud(db_session: Session) -> None:
    admin = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        create_response = client.post(
            "/api/admin/diagnoses",
            json={"code": "A01", "title": "Typhoid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_response.status_code == 201
        diagnosis_id = create_response.json()["id"]

        list_response = client.get(
            "/api/admin/diagnoses",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        update_response = client.patch(
            f"/api/admin/diagnoses/{diagnosis_id}",
            json={"title": "Typhoid fever"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["title"] == "Typhoid fever"

        delete_response = client.delete(
            f"/api/admin/diagnoses/{diagnosis_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()
