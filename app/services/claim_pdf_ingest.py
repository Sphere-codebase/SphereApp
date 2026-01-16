"""PDF claim ingestion service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimLineCoverage,
    ClaimMcpCode,
    ClaimProcedureDiagnosis,
    ClaimProcedureFact,
    ChatMessage,
    ChatSession,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    User,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ParsedLine:
    service_date: date
    mcp_code: str
    dx_codes: list[str]
    reason_codes: list[str]
    billed_cents: int
    allowed_cents: int
    paid_cents: int
    coinsurance_cents: int


@dataclass(frozen=True)
class ParsedPayload:
    account_number: str | None
    patient_first_name: str | None
    patient_last_name: str | None
    patient_dob: date | None
    codes: list[dict[str, Any]]
    lines: list[ParsedLine]
    claim_status: str
    service_date: date
    total_billed_cents: int
    total_allowed_cents: int
    total_paid_cents: int
    total_coinsurance_cents: int


def _parse_date(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} date: {value}",
        ) from exc


def _parse_money(value: str, label: str) -> int:
    cleaned = value.replace("$", "").replace(",", "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing {label} amount",
        )
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} amount: {value}",
        ) from exc
    cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _split_patient_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    normalized = full_name.strip()
    if not normalized:
        return None, None
    if "," in normalized:
        last, first = normalized.split(",", 1)
        return first.strip() or None, last.strip() or None
    parts = normalized.split()
    last_name = parts[-1] if parts else None
    first_name = " ".join(parts[:-1]).strip() if len(parts) > 1 else ""
    return (first_name or None), (last_name or None)


def _normalize_payload(payload: dict[str, Any]) -> ParsedPayload:
    if payload.get("error_message"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=payload.get("error_message"),
        )
    pdf = payload.get("pdf")
    if not isinstance(pdf, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid parser payload",
        )
    info = pdf.get("info")
    if not info:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No claim lines found",
        )

    user_info = pdf.get("user_info") or {}
    account_number = user_info.get("account_number")
    patient_first, patient_last = _split_patient_name(user_info.get("name"))
    dob_value = user_info.get("date_of_birth")
    patient_dob = _parse_date(dob_value, "patient DOB") if dob_value else None

    codes = pdf.get("codes") or []
    claim_status = "PAID" if any(code.get("code") == "F1" for code in codes) else "SUBMITTED"

    lines: list[ParsedLine] = []
    total_billed = 0
    total_allowed = 0
    total_paid = 0
    total_coinsurance = 0
    earliest_date: date | None = None

    for idx, raw in enumerate(info):
        if not isinstance(raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid claim line at index {idx}",
            )
        line_date = _parse_date(raw.get("date", ""), f"service date at index {idx}")
        billed_cents = _parse_money(raw.get("billed_amount", ""), "billed")
        allowed_cents = _parse_money(raw.get("allowed_amount", ""), "allowed")
        paid_cents = _parse_money(raw.get("paid_amount", ""), "paid")

        adjustments = raw.get("adjustments") or []
        coinsurance_cents = 0
        for adj in adjustments:
            if not isinstance(adj, dict):
                continue
            if adj.get("type") == "Patient Responsibility" and adj.get("code") == "COIN":
                coinsurance_cents += _parse_money(adj.get("amount", ""), "coinsurance")

        dx_values = raw.get("dx") or []
        reason_values = raw.get("reason_codes") or []
        dx_codes = [code.strip().upper() for code in dx_values if code and code.strip()]
        reason_codes = [code.strip() for code in reason_values if code and code.strip()]
        mcp_code = str(raw.get("cpt", "")).strip()
        if not mcp_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing CPT code at index {idx}",
            )

        line = ParsedLine(
            service_date=line_date,
            mcp_code=mcp_code,
            dx_codes=dx_codes,
            reason_codes=reason_codes,
            billed_cents=billed_cents,
            allowed_cents=allowed_cents,
            paid_cents=paid_cents,
            coinsurance_cents=coinsurance_cents,
        )
        lines.append(line)

        total_billed += billed_cents
        total_allowed += allowed_cents
        total_paid += paid_cents
        total_coinsurance += coinsurance_cents
        earliest_date = line_date if earliest_date is None else min(earliest_date, line_date)

    if earliest_date is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to determine service date",
        )

    return ParsedPayload(
        account_number=account_number,
        patient_first_name=patient_first,
        patient_last_name=patient_last,
        patient_dob=patient_dob,
        codes=codes,
        lines=lines,
        claim_status=claim_status,
        service_date=earliest_date,
        total_billed_cents=total_billed,
        total_allowed_cents=total_allowed,
        total_paid_cents=total_paid,
        total_coinsurance_cents=total_coinsurance,
    )


def _get_or_create_patient(db: Session, doctor_id: int, payload: ParsedPayload) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.doctor_id == doctor_id,
            Patient.first_name == payload.patient_first_name,
            Patient.last_name == payload.patient_last_name,
            Patient.date_of_birth == payload.patient_dob,
        )
    ).scalar_one_or_none()
    if patient is not None:
        return patient

    patient = Patient(
        id=next_id(db, Patient),
        doctor_id=doctor_id,
        first_name=payload.patient_first_name,
        last_name=payload.patient_last_name,
        date_of_birth=payload.patient_dob,
        created_at=utcnow(),
    )
    db.add(patient)
    return patient


def _get_or_create_insurer(db: Session, name: str) -> InsuranceCompany:
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
    doctor_id: int,
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
            select(func.count(ClaimProcedureFact.id)).where(
                ClaimProcedureFact.claim_id == claim.id
            )
        ).scalar_one()
        if int(existing_count or 0) == line_count:
            return claim
    return None


def _format_cents(value: int) -> str:
    dollars = Decimal(value) / Decimal(100)
    return f"${dollars:,.2f}"


def ingest_parsed_pdf(
    payload: dict[str, Any],
    current_user: User,
    db: Session,
    session_id: int | None = None,
) -> dict[str, Any]:
    logger.info("PDF ingest start doctor_id=%s session_id=%s", current_user.id, session_id)
    parsed = _normalize_payload(payload)
    logger.info(
        "Parsed payload account_number=%s patient_name=%s service_date=%s line_count=%s",
        parsed.account_number,
        " ".join(
            part
            for part in [parsed.patient_first_name or "", parsed.patient_last_name or ""]
            if part
        ).strip(),
        parsed.service_date,
        len(parsed.lines),
    )

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        patient = _get_or_create_patient(db, current_user.id, parsed)
        logger.info("Upserted patient patient_id=%s", patient.id)
        insurer = _get_or_create_insurer(db, "Aetna")
        logger.info("Upserted insurer insurer_id=%s", insurer.id)

        claim = _find_existing_claim(
            db,
            doctor_id=current_user.id,
            patient_id=patient.id,
            insurer_id=insurer.id,
            service_date=parsed.service_date,
            total_billed_cents=parsed.total_billed_cents,
            line_count=len(parsed.lines),
        )
        if claim is None:
            claim = Claim(
                id=next_id(db, Claim),
                doctor_id=current_user.id,
                patient_id=patient.id,
                insurance_company_id=insurer.id,
                created_at=utcnow(),
            )
            db.add(claim)
            db.flush()
            logger.info("Created claim claim_id=%s", claim.id)
        else:
            logger.info("Reused existing claim claim_id=%s", claim.id)

        claim.service_date = parsed.service_date
        claim.claim_status = parsed.claim_status
        claim.billed_amount_total = parsed.total_billed_cents
        claim.allowed_amount_total = parsed.total_allowed_cents
        claim.coinsurance_amount_total = parsed.total_coinsurance_cents
        claim.copay_amount_total = 0
        claim.deductible_amount_total = 0

        # 1. Collect and Normalize all DX codes
        unique_dx_codes: set[str] = set()
        unique_cpt_codes: set[str] = set()

        for line in parsed.lines:
            for dx in line.dx_codes:
                if dx:
                    unique_dx_codes.add(dx)
            unique_cpt_codes.add(line.mcp_code)

        # 2. Upsert Diagnosis Codes FIRST
        # This ensures they exist before any FK references
        if unique_dx_codes:
            db.execute(
                pg_insert(DiagnosisCode)
                .values(
                    [{"code": dx_code, "description": None} for dx_code in unique_dx_codes]
                )
                .on_conflict_do_nothing(index_elements=[DiagnosisCode.code])
            )
            db.flush()  # Critical: ensure diagnosis codes exist before FK inserts
        logger.info("Upserted diagnosis codes dx_count=%s", len(unique_dx_codes))

        # 3. Link Diagnosis Codes to Claim
        if unique_dx_codes:
            db.execute(
                pg_insert(ClaimDiagnosisCode)
                .values(
                    [
                        {"claim_id": claim.id, "diagnosis_code": dx_code}
                        for dx_code in unique_dx_codes
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[ClaimDiagnosisCode.claim_id, ClaimDiagnosisCode.diagnosis_code]
                )
            )
        logger.info("Linked claim diagnosis codes claim_id=%s dx_count=%s", claim.id, len(unique_dx_codes))

        # 4. Upsert MCP Codes
        for cpt_code in sorted(unique_cpt_codes):
            existing = db.execute(
                select(McpCode).where(McpCode.code == cpt_code)
            ).scalar_one_or_none()
            if existing is None:
                db.add(McpCode(code=cpt_code, description=None))
        # Flush not strictly required here unless FKs on lines enforce it immediately, but safer
        db.flush()
        logger.info("Upserted MCP codes cpt_count=%s", len(unique_cpt_codes))

        # 5. Link MCP Codes to Claim
        for cpt_code in sorted(unique_cpt_codes):
            link = db.execute(
                select(ClaimMcpCode).where(
                    ClaimMcpCode.claim_id == claim.id,
                    ClaimMcpCode.mcp_code == cpt_code,
                )
            ).scalar_one_or_none()
            if link is None:
                db.add(ClaimMcpCode(claim_id=claim.id, mcp_code=cpt_code))
        logger.info("Linked MCP codes to claim claim_id=%s cpt_count=%s", claim.id, len(unique_cpt_codes))

        coverage_paid_by_code: dict[str, bool] = {}
        coverage_reasons_by_code: dict[str, list[str]] = {}
        reason_prefixes = []
        for code in parsed.codes:
            code_value = code.get("code")
            if not code_value:
                continue
            code_type = code.get("type")
            prefix = f"{code_type}:{code_value}" if code_type else str(code_value)
            reason_prefixes.append(prefix)

        for line in parsed.lines:
            existing = db.execute(
                select(ClaimProcedureFact).where(
                    ClaimProcedureFact.claim_id == claim.id,
                    ClaimProcedureFact.mcp_code == line.mcp_code,
                    ClaimProcedureFact.service_date == line.service_date,
                    ClaimProcedureFact.billed_amount == line.billed_cents,
                )
            ).scalar_one_or_none()

            # paid_at uses ingestion time for paid lines, else stays null.
            paid_at = utcnow().date() if line.paid_cents > 0 else None
            if existing is None:
                existing = ClaimProcedureFact(
                    id=next_id(db, ClaimProcedureFact),
                    claim_id=claim.id,
                    patient_id=patient.id,
                    insurance_company_id=insurer.id,
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
                db.flush() # Flush to get ID for child items (procedure diagnosis)
            else:
                existing.allowed_amount = line.allowed_cents
                existing.coinsurance_amount = line.coinsurance_cents
                existing.paid_amount = line.paid_cents
                existing.paid_at = paid_at
                existing.units = 1
                existing.patient_id = patient.id
                existing.insurance_company_id = insurer.id
                # No flush needed here as ID exists

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

            has_paid = coverage_paid_by_code.get(line.mcp_code, False)
            coverage_paid_by_code[line.mcp_code] = has_paid or line.paid_cents > 0

            reasons = coverage_reasons_by_code.setdefault(line.mcp_code, [])
            reasons.extend(reason_prefixes)
            reasons.extend(line.reason_codes)
        logger.info("Upserted claim procedure lines claim_id=%s line_count=%s", claim.id, len(parsed.lines))

        for mcp_code, has_paid in coverage_paid_by_code.items():
            status = "PAID" if has_paid else "SUBMITTED"
            if not has_paid and parsed.claim_status == "PAID":
                status = "DENIED_OR_ZERO_PAY"
            raw_reasons = coverage_reasons_by_code.get(mcp_code, [])
            reason_parts = []
            for reason in raw_reasons:
                if reason and reason not in reason_parts:
                    reason_parts.append(reason)
            reason_text = ", ".join(reason_parts) if reason_parts else None

            db.execute(
                pg_insert(ClaimLineCoverage)
                .values(
                    {
                        "claim_id": claim.id,
                        "mcp_code": mcp_code,
                        "status": status,
                        "reason": reason_text,
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
                        "status": status,
                        "reason": reason_text,
                        "policy_link_id": None,
                    },
                )
            )
        logger.info("Upserted claim line coverage claim_id=%s coverage_count=%s", claim.id, len(coverage_paid_by_code))

        chat_session = None
        if session_id:
            chat_session = db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.doctor_id == current_user.id,
                )
            ).scalar_one_or_none()
        if chat_session is None:
            chat_session = (
                db.execute(
                    select(ChatSession)
                    .where(ChatSession.doctor_id == current_user.id)
                    .order_by(ChatSession.created_at.desc())
                )
                .scalars()
                .first()
            )
        if chat_session is None:
            chat_session = ChatSession(
                id=next_id(db, ChatSession),
                doctor_id=current_user.id,
                title=None,
                created_at=utcnow(),
            )
            db.add(chat_session)

        summary = (
            "Claim ingested successfully. "
            f"{len(parsed.lines)} CPT lines processed. "
            f"Totals: billed={_format_cents(parsed.total_billed_cents)}, "
            f"allowed={_format_cents(parsed.total_allowed_cents)}, "
            f"paid={_format_cents(parsed.total_paid_cents)}."
        )
        db.add(
            ChatMessage(
                id=next_id(db, ChatMessage),
                session_id=chat_session.id,
                role="system",
                content=summary,
                created_at=utcnow(),
            )
        )
        logger.info("Logged chat summary session_id=%s claim_id=%s", chat_session.id, claim.id)
    db.commit()

    patient_name = " ".join(
        part for part in [parsed.patient_first_name or "", parsed.patient_last_name or ""] if part
    ).strip()

    return {
        "claim_id": claim.id,
        "patient_id": patient.id,
        "session_id": chat_session.id if chat_session else None,
        "patient_name": patient_name,
        "patient_date_of_birth": parsed.patient_dob,
        "account_number": parsed.account_number,
        "service_date": parsed.service_date,
        "line_count": len(parsed.lines),
        "total_billed_cents": parsed.total_billed_cents,
        "total_allowed_cents": parsed.total_allowed_cents,
        "total_paid_cents": parsed.total_paid_cents,
    }
