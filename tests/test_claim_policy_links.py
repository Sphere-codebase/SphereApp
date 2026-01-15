from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimMcpCode,
    InsuranceCompany,
    McpCode,
    Patient,
    PolicyLink,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.main import app
from app.utils.time import utcnow


def _seed_claim(db_session: Session) -> tuple[User, Claim]:
    doctor_role = db_session.execute(
        select(Role).where(Role.code == "doctor")
    ).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Company A")
    patient = Patient(
        id=next_id(db_session, Patient),
        doctor_id=user.id,
        first_name="Jane",
        last_name="Doe",
        created_at=utcnow(),
    )
    claim = Claim(
        id=next_id(db_session, Claim),
        doctor_id=user.id,
        patient_id=patient.id,
        insurance_company_id=company.id,
        claim_status="DRAFT",
        created_at=utcnow(),
    )
    db_session.add_all([user, UserRole(user_id=user.id, role_id=doctor_role.id), company, patient, claim])
    db_session.commit()
    return user, claim


def test_policy_links_resolution(db_session: Session) -> None:
    user, claim = _seed_claim(db_session)
    code_a = McpCode(code="99213", description="Office Visit")
    code_b = McpCode(code="93000", description="EKG")
    db_session.add_all([code_a, code_b])
    db_session.commit()

    db_session.add_all(
        [
            ClaimMcpCode(claim_id=claim.id, mcp_code=code_a.code),
            ClaimMcpCode(claim_id=claim.id, mcp_code=code_b.code),
            PolicyLink(
                id=next_id(db_session, PolicyLink),
                insurance_company_id=claim.insurance_company_id,
                mcp_code=code_a.code,
                policy_url="https://example.com/policy-a",
                created_at=utcnow(),
            ),
        ]
    )
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/claims/{claim.id}/policy-links",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        by_code = {item["mcp_code"]["code"]: item for item in payload}
        assert by_code["99213"]["policy_url"] == "https://example.com/policy-a"
        assert by_code["99213"]["missing_policy_link"] is False
        assert by_code["93000"]["policy_url"] is None
        assert by_code["93000"]["missing_policy_link"] is True
    finally:
        app.dependency_overrides.clear()
