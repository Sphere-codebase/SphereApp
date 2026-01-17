"""Code repository helpers."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import ClaimDiagnosisCode, ClaimMcpCode, DiagnosisCode, McpCode


def upsert_mcp_codes(db: Session, codes: set[str]) -> None:
    if not codes:
        return
    db.execute(
        pg_insert(McpCode)
        .values([{"code": code, "description": None} for code in sorted(codes)])
        .on_conflict_do_nothing(index_elements=[McpCode.code])
    )


def link_claim_mcp_codes(db: Session, *, claim_id: int, mcp_codes: set[str]) -> None:
    if not mcp_codes:
        return
    db.execute(
        pg_insert(ClaimMcpCode)
        .values([{"claim_id": claim_id, "mcp_code": code} for code in sorted(mcp_codes)])
        .on_conflict_do_nothing(index_elements=[ClaimMcpCode.claim_id, ClaimMcpCode.mcp_code])
    )


def upsert_diagnosis_codes(db: Session, codes: set[str]) -> None:
    if not codes:
        return
    db.execute(
        pg_insert(DiagnosisCode)
        .values([{"code": code, "description": None} for code in sorted(codes)])
        .on_conflict_do_nothing(index_elements=[DiagnosisCode.code])
    )


def link_claim_diagnoses(db: Session, *, claim_id: int, diagnosis_codes: set[str]) -> None:
    if not diagnosis_codes:
        return
    db.execute(
        pg_insert(ClaimDiagnosisCode)
        .values(
            [{"claim_id": claim_id, "diagnosis_code": code} for code in sorted(diagnosis_codes)]
        )
        .on_conflict_do_nothing(
            index_elements=[ClaimDiagnosisCode.claim_id, ClaimDiagnosisCode.diagnosis_code]
        )
    )
