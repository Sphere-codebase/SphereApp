"""Coverage repository helpers."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import ClaimLineCoverage
from app.utils.time import utcnow


def upsert_claim_line_coverage(
    db: Session,
    *,
    claim_id: int,
    clinic_id: int,
    line_coverage: dict[str, tuple[str, str | None]],
) -> None:
    if not line_coverage:
        return

    for mcp_code, (status, reason) in line_coverage.items():
        db.execute(
            pg_insert(ClaimLineCoverage)
            .values(
                {
                    "claim_id": claim_id,
                    "clinic_id": clinic_id,
                    "mcp_code": mcp_code,
                    "status": status,
                    "reason": reason,
                    "policy_link_id": None,
                    "created_at": utcnow(),
                }
            )
            .on_conflict_do_update(
                index_elements=[
                    ClaimLineCoverage.claim_id,
                    ClaimLineCoverage.mcp_code,
                ],
                set_={
                    "clinic_id": clinic_id,
                    "status": status,
                    "reason": reason,
                    "policy_link_id": None,
                },
            )
        )


def upsert_payment_history(db: Session) -> None:
    _ = db
    # No payment history table is available in the current schema.
    return None
