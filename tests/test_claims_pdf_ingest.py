import copy
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import os
from app.core.security import get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimLineCoverage,
    ClaimMcpCode,
    ClaimProcedureDiagnosis,
    ClaimProcedureFact,
    DiagnosisCode,
    McpCode,
    Patient,
    User,
)
from app.parsers.pdf.interface import parse_pdf_document
from app.services.claims.ingestion import ingest_parsed_pdf, ingest_pdf_from_path
from app.utils.time import utcnow

THIS_DIR = Path(__file__).resolve().parent
file_for_test = THIS_DIR / "test_claim.pdf"
SKIP_PDF_TESTS = os.getenv("SKIP_PDF_TESTS") == "1"

def _seed_user(db_session: Session) -> User:
    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _load_sample_payload() -> dict:
    parsed = parse_pdf_document(Path(file_for_test))
    assert parsed.get("error_message") is None
    return parsed


def _count_rows(db_session: Session, model: type) -> int:
    return int(db_session.execute(select(func.count()).select_from(model)).scalar_one())


def test_ingest_pdf_idempotent(db_session: Session) -> None:
    payload = _load_sample_payload()
    user = _seed_user(db_session)

    result = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)

    claim = db_session.execute(select(Claim)).scalar_one()
    assert int(claim.billed_amount_total or 0) == 370000
    assert int(claim.allowed_amount_total or 0) == 45234
    assert int(claim.coinsurance_amount_total or 0) == 9047
    assert claim.claim_status == "PAID"
    assert result["total_paid_cents"] == 36187

    procedures = (
        db_session.execute(
            select(ClaimProcedureFact).where(ClaimProcedureFact.claim_id == claim.id)
        )
        .scalars()
        .all()
    )
    assert len(procedures) == 4

    dx_count = _count_rows(db_session, DiagnosisCode)
    mcp_count = _count_rows(db_session, McpCode)
    claim_dx_count = _count_rows(db_session, ClaimDiagnosisCode)
    claim_mcp_count = _count_rows(db_session, ClaimMcpCode)
    proc_dx_count = _count_rows(db_session, ClaimProcedureDiagnosis)
    coverage_count = _count_rows(db_session, ClaimLineCoverage)
    patient_count = _count_rows(db_session, Patient)

    assert dx_count == 2
    assert mcp_count == 4
    assert claim_dx_count == 2
    assert claim_mcp_count == 4
    assert proc_dx_count == 4
    assert coverage_count == 4
    assert patient_count == 1

    line = db_session.execute(
        select(ClaimProcedureFact).where(ClaimProcedureFact.mcp_code == "98925")
    ).scalar_one()
    assert int(line.coinsurance_amount or 0) == 381

    second = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)
    assert second["claim_id"] == claim.id

    assert _count_rows(db_session, Claim) == 1
    assert _count_rows(db_session, ClaimProcedureFact) == 4
    assert _count_rows(db_session, ClaimDiagnosisCode) == 2
    assert _count_rows(db_session, ClaimMcpCode) == 4
    assert _count_rows(db_session, ClaimProcedureDiagnosis) == 4
    assert _count_rows(db_session, ClaimLineCoverage) == 4
    assert _count_rows(db_session, Patient) == 1


def test_ingest_pdf_rejects_parser_error(db_session: Session) -> None:
    payload = _load_sample_payload()
    user = _seed_user(db_session)
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["error_message"] = "Parser failed"

    with pytest.raises(HTTPException) as exc:
        ingest_parsed_pdf(payload=invalid_payload, current_user=user, db=db_session)

    assert exc.value.status_code == 422


@pytest.mark.skipif(SKIP_PDF_TESTS, reason="PDF ingestion tests disabled by SKIP_PDF_TESTS=1")
def test_ingest_pdf_from_path_happy(db_session: Session) -> None:
    user = _seed_user(db_session)

    result = ingest_pdf_from_path(
        file_path=file_for_test,
        current_user=user,
        db=db_session,
    )

    claim = db_session.execute(select(Claim)).scalar_one()
    assert result["claim_id"] == claim.id


def test_ingest_pdf_from_path_rejects_relative_path(db_session: Session) -> None:
    user = _seed_user(db_session)

    with pytest.raises(HTTPException) as exc:
        ingest_pdf_from_path(
            file_path="relative/path.pdf",
            current_user=user,
            db=db_session,
        )

    assert exc.value.status_code == 400


def test_ingest_pdf_inserts_dx_codes_first(db_session: Session) -> None:
    user = _seed_user(db_session)
    parsed = parse_pdf_document(Path(file_for_test))
    assert parsed.get("error_message") is None

    payload = parsed
    result = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)
    claim_id = result["claim_id"]

    info = payload.get("pdf", {}).get("info", []) or []
    parsed_dx_codes = {
        dx.strip().upper() for item in info for dx in (item.get("dx") or []) if dx and dx.strip()
    }
    assert parsed_dx_codes

    db_dx_codes = {
        row[0]
        for row in db_session.execute(
            select(DiagnosisCode.code).where(DiagnosisCode.code.in_(parsed_dx_codes))
        ).all()
    }
    assert parsed_dx_codes.issubset(db_dx_codes)

    claim_dx_codes = {
        row[0]
        for row in db_session.execute(
            select(ClaimDiagnosisCode.diagnosis_code).where(ClaimDiagnosisCode.claim_id == claim_id)
        ).all()
    }
    assert parsed_dx_codes.issubset(claim_dx_codes)

    dx_count = _count_rows(db_session, DiagnosisCode)
    claim_dx_count = _count_rows(db_session, ClaimDiagnosisCode)
    proc_dx_count = _count_rows(db_session, ClaimProcedureDiagnosis)

    second = ingest_parsed_pdf(payload=payload, current_user=user, db=db_session)
    assert second["claim_id"] == claim_id
    assert _count_rows(db_session, DiagnosisCode) == dx_count
    assert _count_rows(db_session, ClaimDiagnosisCode) == claim_dx_count
    assert _count_rows(db_session, ClaimProcedureDiagnosis) == proc_dx_count
