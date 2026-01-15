import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import (
    Agency,
    AgencyProcedurePolicyLink,
    Claim,
    ClaimProcedure,
    ClaimStatus,
    Patient,
    PolicyLinkStatus,
    ProcedureCode,
    Tenant,
    User,
)
from app.db.session import get_db
from app.main import app


def _seed_claim(db_session: Session) -> tuple[User, Claim]:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant Policies")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    agency = Agency(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Agency A",
        slug="agency-a",
        is_active=True,
    )
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        full_name="Jane Doe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        agency_id=agency.id,
        patient_id=patient.id,
        status=ClaimStatus.DRAFT,
    )
    db_session.add_all([tenant, user, agency, patient, claim])
    db_session.commit()
    return user, claim


def test_policy_links_resolution(db_session: Session) -> None:
    user, claim = _seed_claim(db_session)
    code_a = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=claim.tenant_id,
        code="99213",
        title="Office Visit",
    )
    code_b = ProcedureCode(
        id=uuid.uuid4(),
        tenant_id=claim.tenant_id,
        code="93000",
        title="EKG",
    )
    db_session.add_all([code_a, code_b])
    db_session.commit()

    db_session.add_all(
        [
            ClaimProcedure(
                tenant_id=claim.tenant_id,
                claim_id=claim.id,
                procedure_code_id=code_a.id,
                units=1,
            ),
            ClaimProcedure(
                tenant_id=claim.tenant_id,
                claim_id=claim.id,
                procedure_code_id=code_b.id,
                units=2,
            ),
            AgencyProcedurePolicyLink(
                tenant_id=claim.tenant_id,
                agency_id=claim.agency_id,
                procedure_code_id=code_a.id,
                policy_url="https://example.com/policy-a",
                status=PolicyLinkStatus.ACTIVE,
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
        by_code = {item["procedure_code"]["code"]: item for item in payload}
        assert by_code["99213"]["policy_url"] == "https://example.com/policy-a"
        assert by_code["99213"]["missing_policy_link"] is False
        assert by_code["93000"]["policy_url"] is None
        assert by_code["93000"]["missing_policy_link"] is True
    finally:
        app.dependency_overrides.clear()
