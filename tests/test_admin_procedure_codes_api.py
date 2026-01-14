import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session, is_admin: bool) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Procedure Codes")
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


def test_procedure_codes_requires_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {"code": "99213", "title": "Office Visit"}
        response = client.post(
            "/api/admin/procedure-codes",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()
