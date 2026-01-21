"""PDF claim ingestion service."""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.parsers.pdf.remote_client import parse_pdf_document
from app.repositories import claims as claim_repo
from app.repositories import codes as code_repo
from app.repositories import coverage as coverage_repo
from app.repositories import patients as patient_repo

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


def _format_cents(value: int) -> str:
    dollars = Decimal(value) / Decimal(100)
    return f"${dollars:,.2f}"


def _extract_unique_codes(lines: list[ParsedLine]) -> tuple[set[str], set[str]]:
    unique_dx_codes: set[str] = set()
    unique_mcp_codes: set[str] = set()
    for line in lines:
        for dx in line.dx_codes:
            if dx:
                unique_dx_codes.add(dx)
        unique_mcp_codes.add(line.mcp_code)
    return unique_dx_codes, unique_mcp_codes


def _build_line_coverage(parsed: ParsedPayload) -> dict[str, tuple[str, str | None]]:
    coverage_paid_by_code: dict[str, bool] = {}
    coverage_reasons_by_code: dict[str, list[str]] = {}
    reason_prefixes: list[str] = []

    for code in parsed.codes:
        code_value = code.get("code")
        if not code_value:
            continue
        code_type = code.get("type")
        prefix = f"{code_type}:{code_value}" if code_type else str(code_value)
        reason_prefixes.append(prefix)

    for line in parsed.lines:
        has_paid = coverage_paid_by_code.get(line.mcp_code, False)
        coverage_paid_by_code[line.mcp_code] = has_paid or line.paid_cents > 0

        reasons = coverage_reasons_by_code.setdefault(line.mcp_code, [])
        reasons.extend(reason_prefixes)
        reasons.extend(line.reason_codes)

    line_coverage: dict[str, tuple[str, str | None]] = {}
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
        line_coverage[mcp_code] = (status, reason_text)

    return line_coverage


def ingest_parsed_payload(
    payload: dict[str, Any],
    current_user: User,
    db: Session,
    session_id: int | None = None,
) -> dict[str, Any]:
    logger.info("PDF ingest start doctor_id=%s session_id=%s", current_user.id, session_id)
    parsed = _normalize_payload(payload)
    patient_name = " ".join(
        part for part in [parsed.patient_first_name or "", parsed.patient_last_name or ""] if part
    ).strip()

    unique_dx_codes, unique_mcp_codes = _extract_unique_codes(parsed.lines)
    logger.info(
        "Parsed payload account_number=%s patient_name=%s service_date=%s line_count=%s "
        "dx_count=%s mcp_count=%s",
        parsed.account_number,
        patient_name,
        parsed.service_date,
        len(parsed.lines),
        len(unique_dx_codes),
        len(unique_mcp_codes),
    )

    transaction = db.begin_nested() if db.in_transaction() else db.begin()
    with transaction:
        patient = patient_repo.upsert_patient(
            db,
            doctor_id=current_user.id,
            first_name=parsed.patient_first_name,
            last_name=parsed.patient_last_name,
            date_of_birth=parsed.patient_dob,
        )
        logger.info("Upserted patient patient_id=%s", patient.id)

        insurer = claim_repo.upsert_insurance_company(db, name="Aetna")
        logger.info("Upserted insurer insurer_id=%s", insurer.id)

        claim, created = claim_repo.upsert_claim(
            db,
            doctor_id=current_user.id,
            patient_id=patient.id,
            insurer_id=insurer.id,
            service_date=parsed.service_date,
            claim_status=parsed.claim_status,
            total_billed_cents=parsed.total_billed_cents,
            total_allowed_cents=parsed.total_allowed_cents,
            total_paid_cents=parsed.total_paid_cents,
            total_coinsurance_cents=parsed.total_coinsurance_cents,
            line_count=len(parsed.lines),
        )
        if created:
            logger.info("Created claim claim_id=%s", claim.id)
        else:
            logger.info("Reused existing claim claim_id=%s", claim.id)

        if unique_dx_codes:
            code_repo.upsert_diagnosis_codes(db, unique_dx_codes)
            db.flush()
        logger.info("Upserted diagnosis codes dx_count=%s", len(unique_dx_codes))

        if unique_dx_codes:
            code_repo.link_claim_diagnoses(db, claim_id=claim.id, diagnosis_codes=unique_dx_codes)
        logger.info(
            "Linked claim diagnosis codes claim_id=%s dx_count=%s",
            claim.id,
            len(unique_dx_codes),
        )

        if unique_mcp_codes:
            code_repo.upsert_mcp_codes(db, unique_mcp_codes)
            db.flush()
        logger.info("Upserted MCP codes mcp_count=%s", len(unique_mcp_codes))

        if unique_mcp_codes:
            code_repo.link_claim_mcp_codes(db, claim_id=claim.id, mcp_codes=unique_mcp_codes)
        logger.info(
            "Linked MCP codes to claim claim_id=%s mcp_count=%s",
            claim.id,
            len(unique_mcp_codes),
        )

        claim_repo.upsert_claim_line_items(
            db,
            claim_id=claim.id,
            patient_id=patient.id,
            insurer_id=insurer.id,
            lines=parsed.lines,
        )
        logger.info(
            "Upserted claim procedure lines claim_id=%s line_count=%s",
            claim.id,
            len(parsed.lines),
        )

        line_coverage = _build_line_coverage(parsed)
        coverage_repo.upsert_claim_line_coverage(
            db,
            claim_id=claim.id,
            line_coverage=line_coverage,
        )
        logger.info(
            "Upserted claim line coverage claim_id=%s coverage_count=%s",
            claim.id,
            len(line_coverage),
        )

        chat_session = claim_repo.upsert_chat_session(
            db,
            doctor_id=current_user.id,
            session_id=session_id,
        )

        summary = (
            "Claim ingested successfully. "
            f"{len(parsed.lines)} CPT lines processed. "
            f"Totals: billed={_format_cents(parsed.total_billed_cents)}, "
            f"allowed={_format_cents(parsed.total_allowed_cents)}, "
            f"paid={_format_cents(parsed.total_paid_cents)}."
        )
        claim_repo.add_chat_message(db, session_id=chat_session.id, content=summary)
        logger.info("Logged chat summary session_id=%s claim_id=%s", chat_session.id, claim.id)

    db.commit()
    logger.info(
        "PDF ingest complete claim_id=%s line_count=%s dx_count=%s",
        claim.id,
        len(parsed.lines),
        len(unique_dx_codes),
    )

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


def ingest_parsed_pdf(
    payload: dict[str, Any],
    current_user: User,
    db: Session,
    session_id: int | None = None,
) -> dict[str, Any]:
    return ingest_parsed_payload(
        payload=payload,
        current_user=current_user,
        db=db,
        session_id=session_id,
    )


def ingest_pdf_from_upload(
    *,
    file: UploadFile,
    current_user: User,
    db: Session,
    session_id: int | None = None,
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing PDF")

    with tempfile.TemporaryDirectory() as temp_dir:
        safe_name = Path(file.filename).name
        file_path = Path(temp_dir) / safe_name
        with file_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        file_size = file_path.stat().st_size
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF is empty",
            )
        logger.info(
            "Uploaded PDF filename=%s path=%s size_bytes=%s",
            file.filename,
            file_path,
            file_size,
        )
        parsed = parse_pdf_document(file_path)

    return ingest_parsed_payload(
        payload=parsed,
        current_user=current_user,
        db=db,
        session_id=session_id,
    )


def ingest_pdf_from_path(
    *,
    file_path: str,
    current_user: User,
    db: Session,
    session_id: int | None = None,
) -> dict[str, Any]:
    path = Path(file_path)
    if not path.is_absolute():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_path must be absolute",
        )
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_path does not exist",
        )
    if path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_path must end with .pdf",
        )

    logger.info(
        "Local PDF ingest file_path=%s size_bytes=%s",
        path,
        path.stat().st_size,
    )

    try:
        parsed = parse_pdf_document(path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parser failed: {exc}",
        ) from exc

    info = parsed.get("pdf", {}).get("info", []) if isinstance(parsed, dict) else []
    dx_codes = {
        dx.strip().upper()
        for item in info
        if isinstance(item, dict)
        for dx in (item.get("dx") or [])
        if isinstance(dx, str) and dx.strip()
    }
    user_info = parsed.get("pdf", {}).get("user_info", {}) if isinstance(parsed, dict) else {}
    patient_name = user_info.get("name")
    logger.info(
        "Local PDF parsed account_number=%s patient_name=%s service_date=%s "
        "cpt_count=%s dx_count=%s",
        user_info.get("account_number"),
        patient_name,
        info[0].get("date") if info else None,
        len(info),
        len(dx_codes),
    )

    result = ingest_parsed_payload(
        payload=parsed,
        current_user=current_user,
        db=db,
        session_id=session_id,
    )

    return {
        **result,
        "cpt_line_count": result.get("line_count"),
        "dx_code_count": len(dx_codes),
    }
