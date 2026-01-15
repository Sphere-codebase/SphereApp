import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agency, Claim, ClaimStatus, Patient, Tenant, User


def test_migrations_and_crud(db_session: Session) -> None:
    tenant = Tenant(id=uuid.uuid4(), name="Tenant A")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="doctor@example.com",
        hashed_password="hashed",
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

    loaded_claim = db_session.execute(select(Claim).where(Claim.id == claim.id)).scalar_one()
    assert loaded_claim.tenant_id == tenant.id
