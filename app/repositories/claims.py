"""Claim repository helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import (
    ChatMessage,
    ChatSession,
    Claim,
    ClaimProcedureDiagnosis,
    ClaimProcedureFact,
    InsuranceCompany,
    Patient,
)
from app.utils.time import utcnow


class ClaimLineItem(Protocol):
    service_date: date
    mcp_code: str
    dx_codes: list[str]
    billed_cents: int
    allowed_cents: int
    paid_cents: int
    coinsurance_cents: int


def upsert_insurance_company(db: Session, *, name: str) -> InsuranceCompany:
    insurer = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.name == name)
    ).scalar_one_or_none()
    if insurer is not None:
        return insurer
    insurer = InsuranceCompany(
        id=next_id(db, InsuranceCompany),
        name=name,
        created_at=utcnow(),
    )
    db.add(insurer)
    return insurer


def _find_existing_claim(
    db: Session,
    *,
    doctor_id: int,
    clinic_id: int,
    patient_id: int,
    insurer_id: int,
    service_date: date,
    total_billed_cents: int,
    line_count: int,
) -> Claim | None:
    candidates = (
        db.execute(
            select(Claim).where(
                Claim.doctor_id == doctor_id,
                Claim.clinic_id == clinic_id,
                Claim.patient_id == patient_id,
                Claim.insurance_company_id == insurer_id,
                Claim.service_date == service_date,
                Claim.billed_amount_total == total_billed_cents,
            )
        )
        .scalars()
        .all()
    )
    for claim in candidates:
        existing_count = db.execute(
            select(func.count(ClaimProcedureFact.id)).where(ClaimProcedureFact.claim_id == claim.id)
        ).scalar_one()
        if int(existing_count or 0) == line_count:
            return claim
    return None


def upsert_claim(
    db: Session,
    *,
    doctor_id: int,
    clinic_id: int,
    patient_id: int,
    insurer_id: int,
    service_date: date,
    claim_status: str,
    total_billed_cents: int,
    total_allowed_cents: int,
    total_paid_cents: int,
    total_coinsurance_cents: int,
    line_count: int,
) -> tuple[Claim, bool]:
    claim = _find_existing_claim(
        db,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        patient_id=patient_id,
        insurer_id=insurer_id,
        service_date=service_date,
        total_billed_cents=total_billed_cents,
        line_count=line_count,
    )
    created = False
    if claim is None:
        claim = Claim(
            id=next_id(db, Claim),
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            insurance_company_id=insurer_id,
            created_at=utcnow(),
        )
        db.add(claim)
        created = True

    claim.service_date = service_date
    claim.claim_status = claim_status
    claim.clinic_id = clinic_id
    claim.billed_amount_total = total_billed_cents
    claim.allowed_amount_total = total_allowed_cents
    claim.coinsurance_amount_total = total_coinsurance_cents
    claim.copay_amount_total = 0
    claim.deductible_amount_total = 0
    return claim, created


def upsert_claim_line_items(
    db: Session,
    *,
    claim_id: int,
    patient_id: int,
    insurer_id: int,
    clinic_id: int,
    lines: Iterable[ClaimLineItem],
) -> None:
    for line in lines:
        existing = db.execute(
            select(ClaimProcedureFact).where(
                ClaimProcedureFact.claim_id == claim_id,
                ClaimProcedureFact.clinic_id == clinic_id,
                ClaimProcedureFact.mcp_code == line.mcp_code,
                ClaimProcedureFact.service_date == line.service_date,
                ClaimProcedureFact.billed_amount == line.billed_cents,
            )
        ).scalar_one_or_none()

        paid_at = utcnow().date() if line.paid_cents > 0 else None
        if existing is None:
            existing = ClaimProcedureFact(
                id=next_id(db, ClaimProcedureFact),
                claim_id=claim_id,
                patient_id=patient_id,
                insurance_company_id=insurer_id,
                clinic_id=clinic_id,
                mcp_code=line.mcp_code,
                service_date=line.service_date,
                units=1,
                billed_amount=line.billed_cents,
                allowed_amount=line.allowed_cents,
                coinsurance_amount=line.coinsurance_cents,
                copay_amount=None,
                deductible_amount=None,
                paid_amount=line.paid_cents,
                paid_at=paid_at,
                created_at=utcnow(),
            )
            db.add(existing)
            db.flush()
        else:
            existing.allowed_amount = line.allowed_cents
            existing.coinsurance_amount = line.coinsurance_cents
            existing.paid_amount = line.paid_cents
            existing.paid_at = paid_at
            existing.units = 1
            existing.patient_id = patient_id
            existing.insurance_company_id = insurer_id
            existing.clinic_id = clinic_id

        if line.dx_codes:
            db.execute(
                pg_insert(ClaimProcedureDiagnosis)
                .values(
                    [
                        {
                            "claim_procedure_fact_id": existing.id,
                            "diagnosis_code": dx_code,
                        }
                        for dx_code in line.dx_codes
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ClaimProcedureDiagnosis.claim_procedure_fact_id,
                        ClaimProcedureDiagnosis.diagnosis_code,
                    ]
                )
            )


def upsert_chat_session(
    db: Session,
    *,
    doctor_id: int,
    clinic_id: int,
    session_id: int | None,
) -> ChatSession:
    chat_session = None
    if session_id:
        chat_session = db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.doctor_id == doctor_id,
                ChatSession.clinic_id == clinic_id,
            )
        ).scalar_one_or_none()
    if chat_session is None:
        chat_session = (
            db.execute(
                select(ChatSession)
                .where(
                    ChatSession.doctor_id == doctor_id,
                    ChatSession.clinic_id == clinic_id,
                )
                .order_by(ChatSession.created_at.desc())
            )
            .scalars()
            .first()
        )
    if chat_session is None:
        chat_session = ChatSession(
            id=next_id(db, ChatSession),
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            title=None,
            created_at=utcnow(),
        )
        db.add(chat_session)
    return chat_session


def add_chat_message(
    db: Session,
    *,
    session_id: int,
    clinic_id: int,
    content: str,
) -> ChatMessage:
    message = ChatMessage(
        id=next_id(db, ChatMessage),
        session_id=session_id,
        clinic_id=clinic_id,
        role="system",
        content=content,
        created_at=utcnow(),
    )
    db.add(message)
    return message


class ClaimsRepository:
    @staticmethod
    def list_my_claims_summary(
        db: Session,
        *,
        doctor_id: int,
        clinic_id: int,
        limit: int,
        offset: int,
        q: str | None,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[list[tuple[Claim, Patient, InsuranceCompany, float, float]], int]:
        patient_name = func.trim(
            func.concat(
                func.coalesce(Patient.first_name, ""),
                " ",
                func.coalesce(Patient.last_name, ""),
            )
        )

        base_stmt = select(Claim.id).join(Patient, Claim.patient_id == Patient.id)
        base_stmt = base_stmt.where(
            Claim.doctor_id == doctor_id,
            Claim.clinic_id == clinic_id,
        )
        if q:
            like = f"%{q}%"
            base_stmt = base_stmt.where(
                or_(patient_name.ilike(like), Claim.claim_number.ilike(like))
            )
        if date_from:
            base_stmt = base_stmt.where(Claim.service_date >= date_from)
        if date_to:
            base_stmt = base_stmt.where(Claim.service_date <= date_to)

        total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

        sums_subquery = (
            select(
                ClaimProcedureFact.claim_id.label("claim_id"),
                func.coalesce(func.sum(ClaimProcedureFact.billed_amount), 0).label(
                    "requested_total"
                ),
                func.coalesce(func.sum(ClaimProcedureFact.allowed_amount), 0).label(
                    "approved_total"
                ),
            )
            .group_by(ClaimProcedureFact.claim_id)
            .subquery()
        )

        requested_total = func.coalesce(sums_subquery.c.requested_total, 0).label("requested_total")
        approved_total = func.coalesce(sums_subquery.c.approved_total, 0).label("approved_total")

        stmt = (
            select(Claim, Patient, InsuranceCompany, requested_total, approved_total)
            .join(Patient, Claim.patient_id == Patient.id)
            .join(InsuranceCompany, Claim.insurance_company_id == InsuranceCompany.id)
            .outerjoin(sums_subquery, sums_subquery.c.claim_id == Claim.id)
            .where(Claim.doctor_id == doctor_id, Claim.clinic_id == clinic_id)
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(patient_name.ilike(like), Claim.claim_number.ilike(like)))
        if date_from:
            stmt = stmt.where(Claim.service_date >= date_from)
        if date_to:
            stmt = stmt.where(Claim.service_date <= date_to)

        stmt = stmt.order_by(Claim.service_date.desc().nullslast(), Claim.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        rows = db.execute(stmt).all()
        return rows, int(total or 0)
