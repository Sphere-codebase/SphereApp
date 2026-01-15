import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session, is_admin: bool) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Admin Agencies")
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


def test_agencies_requires_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/admin/agencies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()


def test_create_agency_duplicate_slug(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {"name": "Agency A", "slug": "agency-a", "is_active": True}
        first = client.post(
            "/api/admin/agencies",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/admin/agencies",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "AGENCY_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_create_agency_generates_unique_slug(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        first = client.post(
            "/api/admin/agencies",
            json={"name": "Aetna Insurance", "is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201
        assert first.json()["slug"] == "aetna-insurance"

        second = client.post(
            "/api/admin/agencies",
            json={"name": "Aetna Insurance", "is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 201
        assert second.json()["slug"] == "aetna-insurance-2"
    finally:
        app.dependency_overrides.clear()


def test_update_agency_name_does_not_change_slug(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        created = client.post(
            "/api/admin/agencies",
            json={"name": "Agency A", "slug": "agency-a", "is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 201
        agency_id = created.json()["id"]

        updated = client.patch(
            f"/api/admin/agencies/{agency_id}",
            json={"name": "Agency A Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert updated.status_code == 200
        assert updated.json()["slug"] == "agency-a"
    finally:
        app.dependency_overrides.clear()


def test_update_agency_duplicate_slug_returns_409(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        first = client.post(
            "/api/admin/agencies",
            json={"name": "Agency One", "slug": "agency-one", "is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/admin/agencies",
            json={"name": "Agency Two", "slug": "agency-two", "is_active": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 201
        agency_id = second.json()["id"]

        conflict = client.patch(
            f"/api/admin/agencies/{agency_id}",
            json={"slug": "agency-one"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "AGENCY_EXISTS"
    finally:
        app.dependency_overrides.clear()
