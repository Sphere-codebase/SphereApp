from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_user(db_session: Session, is_admin: bool) -> User:
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
        email="admin@example.com" if is_admin else "member@example.com",
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


def test_insurance_companies_requires_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/admin/insurance-companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()


def test_create_insurance_company_duplicate_name(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        payload = {"name": "Company A"}
        first = client.post(
            "/api/admin/insurance-companies",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/admin/insurance-companies",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "INSURANCE_COMPANY_EXISTS"
    finally:
        app.dependency_overrides.clear()


def test_update_insurance_company_name(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        created = client.post(
            "/api/admin/insurance-companies",
            json={"name": "Company A"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 201
        company_id = created.json()["id"]

        updated = client.patch(
            f"/api/admin/insurance-companies/{company_id}",
            json={"name": "Company A Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Company A Updated"
    finally:
        app.dependency_overrides.clear()
