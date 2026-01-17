from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimLineCoverage,
    ClaimMcpCode,
    User,
)
from app.services.claims.ingestion import ingest_pdf_from_path
from app.utils.time import utcnow

_FILE_FOR_TEST = Path("/Users/user/Developer/pythonProject/SphereApp/tests/test_claim.pdf")


def _seed_user(db_session: Session) -> User:
    user = User(
        id=next_id(db_session, User),
        email="doctor_idempotent@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _count_rows(db_session: Session, model: type) -> int:
    return int(db_session.execute(select(func.count()).select_from(model)).scalar_one())


def test_ingest_pdf_twice_idempotent(db_session: Session) -> None:
    user = _seed_user(db_session)

    first = ingest_pdf_from_path(
        file_path=str(_FILE_FOR_TEST),
        current_user=user,
        db=db_session,
    )

    assert _count_rows(db_session, Claim) == 1
    assert _count_rows(db_session, ClaimMcpCode) > 0
    assert _count_rows(db_session, ClaimDiagnosisCode) > 0
    assert _count_rows(db_session, ClaimLineCoverage) > 0

    claim_count = _count_rows(db_session, Claim)
    claim_mcp_count = _count_rows(db_session, ClaimMcpCode)
    claim_dx_count = _count_rows(db_session, ClaimDiagnosisCode)
    claim_coverage_count = _count_rows(db_session, ClaimLineCoverage)

    second = ingest_pdf_from_path(
        file_path=str(_FILE_FOR_TEST),
        current_user=user,
        db=db_session,
    )

    assert first["claim_id"] == second["claim_id"]
    assert _count_rows(db_session, Claim) == claim_count
    assert _count_rows(db_session, ClaimMcpCode) == claim_mcp_count
    assert _count_rows(db_session, ClaimDiagnosisCode) == claim_dx_count
    assert _count_rows(db_session, ClaimLineCoverage) == claim_coverage_count


def test_ingest_pdf_from_path_rejects_relative_path(db_session: Session) -> None:
    user = _seed_user(db_session)

    with pytest.raises(HTTPException) as exc:
        ingest_pdf_from_path(
            file_path="relative/path.pdf",
            current_user=user,
            db=db_session,
        )

    assert exc.value.status_code == 400


def test_ingest_pdf_from_path_rejects_non_pdf(db_session: Session, tmp_path: Path) -> None:
    user = _seed_user(db_session)
    file_path = tmp_path / "not_a_pdf.txt"
    file_path.write_text("not a pdf")

    with pytest.raises(HTTPException) as exc:
        ingest_pdf_from_path(
            file_path=str(file_path),
            current_user=user,
            db=db_session,
        )

    assert exc.value.status_code == 400
