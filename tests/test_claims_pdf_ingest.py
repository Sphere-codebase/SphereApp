import copy
import json
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
    ClaimProcedureDiagnosis,
    ClaimProcedureFact,
    DiagnosisCode,
    McpCode,
    Patient,
    User,
)
from app.services.claim_pdf_ingest import ingest_parsed_pdf
from app.utils.time import utcnow


def _load_sample_payload() -> dict:
    path = Path(__file__).resolve().parents[1] / "dlc-modul" / "example.txt"
    return json.loads(path.read_text())


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
        db_session.execute(select(ClaimProcedureFact).where(ClaimProcedureFact.claim_id == claim.id))
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
