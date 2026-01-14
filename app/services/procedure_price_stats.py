"""Utilities for procedure pricing aggregates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimProcedure, ProcedurePriceByAgency
from app.db.session import SessionLocal


def _recompute_with_session(
    db: Session,
    tenant_id: UUID,
    agency_id: UUID,
    procedure_code_id: UUID,
) -> None:
    stmt = (
        select(
            func.count(ClaimProcedure.id),
            func.min(ClaimProcedure.paid_amount_cents),
            func.max(ClaimProcedure.paid_amount_cents),
            func.avg(ClaimProcedure.paid_amount_cents),
        )
        .join(Claim, ClaimProcedure.claim_id == Claim.id)
        .where(
            ClaimProcedure.tenant_id == tenant_id,
            ClaimProcedure.procedure_code_id == procedure_code_id,
            Claim.tenant_id == tenant_id,
            Claim.agency_id == agency_id,
            ClaimProcedure.paid_amount_cents.is_not(None),
        )
    )
    count, min_paid, max_paid, avg_paid = db.execute(stmt).one()
    existing = db.execute(
        select(ProcedurePriceByAgency).where(
            ProcedurePriceByAgency.tenant_id == tenant_id,
            ProcedurePriceByAgency.agency_id == agency_id,
            ProcedurePriceByAgency.procedure_code_id == procedure_code_id,
        )
    ).scalar_one_or_none()

    if not count:
        if existing is not None:
            db.delete(existing)
        db.commit()
        return

    avg_value = int(round(float(avg_paid)))
    record = existing or ProcedurePriceByAgency(
        tenant_id=tenant_id,
        agency_id=agency_id,
        procedure_code_id=procedure_code_id,
        avg_paid_cents=avg_value,
        min_paid_cents=int(min_paid),
        max_paid_cents=int(max_paid),
        claims_count=int(count),
    )
    record.avg_paid_cents = avg_value
    record.min_paid_cents = int(min_paid)
    record.max_paid_cents = int(max_paid)
    record.claims_count = int(count)
    db.add(record)
    db.commit()


def recompute_procedure_price_stats(
    tenant_id: UUID,
    agency_id: UUID,
    procedure_code_id: UUID,
) -> None:
    """Recompute cached pricing aggregates for one procedure within an agency."""

    db = SessionLocal()
    try:
        _recompute_with_session(db, tenant_id, agency_id, procedure_code_id)
    finally:
        db.close()
