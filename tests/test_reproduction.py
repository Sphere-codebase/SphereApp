from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import Claim, ClaimDiagnosisCode, DiagnosisCode, User
from app.services.claims.ingestion import ingest_parsed_pdf
from app.utils.time import utcnow


def _seed_user(db_session: Session) -> User:
    user = User(
        id=next_id(db_session, User),
        email="doctor_repro@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_ingest_pdf_regression_m4696(db_session: Session) -> None:
    """
    reproduce_issue: ForeignKeyViolation on claim_diagnosis_codes.diagnosis_code
    when diagnosis code does not exist.
    """
    user = _seed_user(db_session)

    # Payload with dx codes that likely don't exist in the seeded DB (or empty DB)
    # Using mixed case to also test normalization requirement
    dx_code_1 = "M46.96"
    dx_code_2 = "m47.816"  # mixed case, should be normalized to M47.816

    payload = {
        "pdf": {
            "user_info": {"name": "Test Patient", "date_of_birth": "01/01/1980"},
            "codes": [],
            "info": [
                {
                    "date": "01/01/2023",
                    "billed_amount": "100.00",
                    "allowed_amount": "80.00",
                    "paid_amount": "70.00",
                    "cpt": "99213",
                    "dx": [dx_code_1, dx_code_2],
                    "reason_codes": [],
                }
            ],
        }
    }

    # This should succeed if fixed, or fail with IntegrityError if regression exists
    result = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)

    # Assertions
    claim_id = result["claim_id"]
    claim = db_session.get(Claim, claim_id)
    assert claim is not None

    # Verify DiagnosisCode existence and normalization
    dc1 = db_session.get(DiagnosisCode, dx_code_1.upper())
    dc2 = db_session.get(DiagnosisCode, dx_code_2.upper())
    assert dc1 is not None, f"DiagnosisCode {dx_code_1} missing"
    assert dc2 is not None, f"DiagnosisCode {dx_code_2} missing"

    # Verify links
    links = (
        db_session.execute(
            select(ClaimDiagnosisCode).where(ClaimDiagnosisCode.claim_id == claim_id)
        )
        .scalars()
        .all()
    )

    linked_codes = {link.diagnosis_code for link in links}
    assert dx_code_1.upper() in linked_codes
    assert dx_code_2.upper() in linked_codes

    # Verify Idempotency
    # Ingesting again should not raise error and should not duplicate
    ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)

    links_after = (
        db_session.execute(
            select(ClaimDiagnosisCode).where(ClaimDiagnosisCode.claim_id == claim_id)
        )
        .scalars()
        .all()
    )
    assert len(links_after) == len(links)
