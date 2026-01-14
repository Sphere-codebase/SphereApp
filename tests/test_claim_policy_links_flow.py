import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_users(db_session: Session) -> tuple[User, User]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Policy Flow")
    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=True,
    )
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
        is_admin=False,
    )
    db_session.add_all([tenant, admin, user])
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
        agency_response = client.post(
            "/api/admin/agencies",
            json={"name": "Agency A", "slug": "agency-a", "is_active": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert agency_response.status_code == 201
        agency_id = agency_response.json()["id"]

        code_response = client.post(
            "/api/admin/procedure-codes",
            json={"code": "99213", "title": "Office Visit", "category": "Evaluation"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert code_response.status_code == 201
        procedure_id = code_response.json()["id"]

        missing_code_response = client.post(
            "/api/admin/procedure-codes",
            json={"code": "93000", "title": "EKG", "category": "Cardiology"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert missing_code_response.status_code == 201
        missing_procedure_id = missing_code_response.json()["id"]

        link_response = client.post(
            "/api/admin/policy-links",
            json={
                "agency_id": agency_id,
                "procedure_code_id": procedure_id,
                "policy_url": "https://example.com/policy-a",
                "status": "ACTIVE",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert link_response.status_code == 201

        patient_response = client.post(
            "/api/patients",
            json={"first_name": "Jane", "last_name": "Doe", "sex": "F"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert patient_response.status_code == 201
        patient_id = patient_response.json()["id"]

        visit_response = client.post(
            f"/api/patients/{patient_id}/visits",
            json={
                "visited_at": datetime.now(tz=UTC).isoformat(),
                "provider": "Dr. House",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert visit_response.status_code == 201
        visit_id = visit_response.json()["id"]

        claim_response = client.post(
            "/api/claims",
            json={"agency_id": agency_id, "patient_id": patient_id},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert claim_response.status_code == 201
        claim_id = claim_response.json()["id"]

        attach_response = client.post(
            f"/api/claims/{claim_id}/visits",
            json={"visit_ids": [visit_id]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert attach_response.status_code == 200

        procedures_response = client.post(
            f"/api/claims/{claim_id}/procedures",
            json={
                "procedures": [
                    {"procedure_code_id": procedure_id, "units": 1},
                    {"procedure_code_id": missing_procedure_id, "units": 1},
                ]
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert procedures_response.status_code == 200

        policy_links_response = client.get(
            f"/api/claims/{claim_id}/policy-links",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert policy_links_response.status_code == 200
        items = policy_links_response.json()
        by_code = {item["procedure_code"]["code"]: item for item in items}

        assert by_code["99213"]["policy_url"] == "https://example.com/policy-a"
        assert by_code["99213"]["missing_policy_link"] is False
        assert by_code["93000"]["policy_url"] is None
        assert by_code["93000"]["missing_policy_link"] is True
    finally:
        app.dependency_overrides.clear()
