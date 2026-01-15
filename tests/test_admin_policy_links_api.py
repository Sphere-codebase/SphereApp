import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Agency, ProcedureCode, Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_admin(db_session: Session) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Admin Policies")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def _seed_user(db_session: Session, is_admin: bool) -> User:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Policy Links")
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


def test_policy_link_unique_active(db_session: Session) -> None:
    user = _seed_admin(db_session)
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Agency A",
        slug="agency-a",
        is_active=True,
    )
    code = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        code="99213",
        title="Office Visit",
    )
    db_session.add_all([agency, code])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {
            "agency_id": str(agency.id),
            "procedure_code_id": str(code.id),
            "policy_url": "https://example.com/policy",
            "status": "ACTIVE",
        }
        first = client.post(
            "/api/admin/policy-links",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/admin/policy-links",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "POLICY_LINK_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_policy_link_invalid_fk_returns_404(db_session: Session) -> None:
    user = _seed_admin(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {
            "agency_id": str(uuid.uuid4()),
            "procedure_code_id": str(uuid.uuid4()),
            "policy_url": "https://example.com/policy",
            "status": "ACTIVE",
        }
        response = client.post(
            "/api/admin/policy-links",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_policy_links_require_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Agency A",
        slug="agency-a",
        is_active=True,
    )
    code = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        code="99213",
        title="Office Visit",
    )
    db_session.add_all([agency, code])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {
            "agency_id": str(agency.id),
            "procedure_code_id": str(code.id),
            "policy_url": "https://example.com/policy",
            "status": "ACTIVE",
        }
        response = client.post(
            "/api/admin/policy-links",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()
