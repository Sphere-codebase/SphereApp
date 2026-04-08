from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Clinic, User
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_clinic(db_session: Session, name: str = "Clinic A") -> Clinic:
    clinic = Clinic(id=next_id(db_session, Clinic), name=name, created_at=utcnow())
    db_session.add(clinic)
    db_session.flush()
    return clinic


def _seed_user(db_session: Session, email: str, role: str, clinic_id: int) -> User:
    user = User(
        id=next_id(db_session, User),
        email=email,
        password_hash=get_password_hash("secret"),
        full_name="Test User",
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


def test_doctor_dashboard_allows_doctor_and_returns_empty_state(db_session: Session) -> None:
    clinic = _seed_clinic(db_session)
    doctor = _seed_user(db_session, "doctor@example.com", "doctor", clinic.id)
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    token = create_access_token(str(doctor.id))
    try:
        response = client.get(
            "/api/dashboard/doctor",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["doctor"]["id"] == doctor.id
        assert payload["active_sessions"] == []
        assert payload["recent_claims"] == []
    finally:
        app.dependency_overrides.clear()


def test_clinic_dashboard_allows_clinic_admin_with_live_query_params(db_session: Session) -> None:
    clinic = _seed_clinic(db_session)
    clinic_admin = _seed_user(
        db_session, "clinic-admin@example.com", "clinic_admin", clinic.id
    )
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    token = create_access_token(str(clinic_admin.id))
    try:
        response = client.get(
            "/api/clinic/dashboard?from=2026-03-01&to=2026-03-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["range"] == {"from": "2026-03-01", "to": "2026-03-31"}
        assert payload["kpis"]["total_claims"] == 0
        assert payload["top_insurers"] == []
    finally:
        app.dependency_overrides.clear()


def test_doctor_dashboard_rejects_platform_staff_admin(db_session: Session) -> None:
    clinic = _seed_clinic(db_session)
    platform_admin = _seed_user(
        db_session, "platform@example.com", "platform_staff_admin", clinic.id
    )
    db_session.commit()

    _override_db(db_session)
    client = TestClient(app)
    token = create_access_token(str(platform_admin.id))
    try:
        response = client.get(
            "/api/dashboard/doctor",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_403"
    finally:
        app.dependency_overrides.clear()
