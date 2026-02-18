from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import Role, User, UserRole
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_users(db_session: Session) -> tuple[User, User]:
    admin_role = db_session.execute(select(Role).where(Role.code == "admin")).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(id=next_id(db_session, Role), code="admin", description="Admin")
        db_session.add(admin_role)
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
    db_session.flush()

    first_user_id = next_id(db_session, User)
    admin = User(
        id=first_user_id,
        email="admin@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        role="platform_staff_admin",
        created_at=utcnow(),
    )
    user = User(
        id=first_user_id + 1,
        email="doctor@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        role="doctor",
        created_at=utcnow(),
    )
    db_session.add_all([admin, user])
    db_session.flush()
    db_session.add_all(
        [
            UserRole(user_id=admin.id, role_id=doctor_role.id),
            UserRole(user_id=admin.id, role_id=admin_role.id),
            UserRole(user_id=user.id, role_id=doctor_role.id),
        ]
    )
    db_session.commit()
    return admin, user


def test_policy_links_flow(db_session: Session) -> None:
    admin, user = _seed_users(db_session)
    admin_token = create_access_token(str(admin.id))
    user_token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        company_response = client.post(
            "/api/admin/insurance-companies",
            json={"name": "Company A"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert company_response.status_code == 201
        company_id = company_response.json()["id"]

        code_response = client.post(
            "/api/admin/mcp-codes",
            json={"code": "99213", "description": "Office Visit"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert code_response.status_code == 201

        missing_code_response = client.post(
            "/api/admin/mcp-codes",
            json={"code": "93000", "description": "EKG"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert missing_code_response.status_code == 201

        link_response = client.post(
            "/api/admin/policy-links",
            json={
                "insurance_company_id": company_id,
                "mcp_code": "99213",
                "policy_url": "https://example.com/policy-a",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert link_response.status_code == 201

        patient_response = client.post(
            "/api/patients",
            json={"first_name": "Jane", "last_name": "Doe"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert patient_response.status_code == 201
        patient_id = patient_response.json()["id"]

        claim_response = client.post(
            "/api/claims",
            json={"insurance_company_id": company_id, "patient_id": patient_id},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert claim_response.status_code == 201
        claim_id = claim_response.json()["id"]

        procedures_response = client.post(
            f"/api/claims/{claim_id}/mcp-codes",
            json={"mcp_codes": ["99213", "93000"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert procedures_response.status_code == 200

        policy_links_response = client.get(
            f"/api/claims/{claim_id}/policy-links",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert policy_links_response.status_code == 200
        items = policy_links_response.json()
        by_code = {item["mcp_code"]["code"]: item for item in items}

        assert by_code["99213"]["policy_url"] == "https://example.com/policy-a"
        assert by_code["99213"]["missing_policy_link"] is False
        assert by_code["93000"]["policy_url"] is None
        assert by_code["93000"]["missing_policy_link"] is True
    finally:
        app.dependency_overrides.clear()
