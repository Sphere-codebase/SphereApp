from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Clinic, User
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str) -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session: Session, email: str, role: str, clinic_id: int) -> User:
    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=clinic_id,
        role=role,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _override_db(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


def test_admin_directory_requires_platform_staff_admin(db_session: Session) -> None:
    clinic = _seed_clinic(db_session, "Clinic A")
    doctor = _seed_user(db_session, "doctor@example.com", "doctor", clinic.id)
    chief = _seed_user(db_session, "chief@example.com", "chief_doctor", clinic.id)
    clinic_admin = _seed_user(db_session, "admin@example.com", "clinic_admin", clinic.id)
    platform_admin = _seed_user(
        db_session, "platform@example.com", "platform_staff_admin", clinic.id
    )
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    try:
        for user in [doctor, chief, clinic_admin]:
            token = create_access_token(str(user.id))
            response = client.get(
                "/api/admin/insurance-companies",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403

        token = create_access_token(str(platform_admin.id))
        response = client.get(
            "/api/admin/insurance-companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
