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
        clinic_id=1,
        role="platform_staff_admin" if is_admin else "doctor",
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if is_admin:
        db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db_session.commit()
    return user


def test_diagnosis_codes_require_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/admin/diagnosis-codes",
            json={"code": "A00", "description": "Cholera"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()


def test_admin_diagnosis_codes_crud(db_session: Session) -> None:
    admin = _seed_user(db_session, is_admin=True)
    token = create_access_token(str(admin.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        create_response = client.post(
            "/api/admin/diagnosis-codes",
            json={"code": "A01", "description": "Typhoid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_response.status_code == 201
        diagnosis_code = create_response.json()["code"]

        list_response = client.get(
            "/api/admin/diagnosis-codes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        update_response = client.patch(
            f"/api/admin/diagnosis-codes/{diagnosis_code}",
            json={"description": "Typhoid fever"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["description"] == "Typhoid fever"

        delete_response = client.delete(
            f"/api/admin/diagnosis-codes/{diagnosis_code}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()
