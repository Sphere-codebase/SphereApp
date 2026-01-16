from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Claim, InsuranceCompany, Patient, User
from app.utils.time import utcnow


def test_migrations_and_crud(db_session: Session) -> None:
    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash="hashed",
        is_active=True,
        created_at=utcnow(),
    )
    company = InsuranceCompany(
        id=next_id(db_session, InsuranceCompany),
        name="Company A",
        created_at=utcnow(),
    )
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

    db_session.add_all([user, company, patient, claim])
    db_session.commit()

    loaded_claim = db_session.execute(select(Claim).where(Claim.id == claim.id)).scalar_one()
    assert loaded_claim.doctor_id == user.id
