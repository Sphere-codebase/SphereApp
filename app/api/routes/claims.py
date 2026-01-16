"""Claim endpoints."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.core.security import get_current_user
from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimMcpCode,
    InsuranceCompany,
    McpCode,
    Patient,
    PolicyLink,
    User,
)
from app.db.session import get_db
from app.schemas.claims import (
    ClaimCreateRequest,
    ClaimMcpCodeCreateRequest,
    ClaimMcpCodeResponse,
    ClaimPolicyLinkItem,
    ClaimPdfIngestResponse,
    ClaimResponse,
    ClaimUpdateRequest,
    McpCodeSummary,
)
from app.services.claim_pdf_ingest import ingest_parsed_pdf
from app.services.pdf_parser_client import parse_pdf_document
from app.utils.time import utcnow

router = APIRouter(prefix="/api/claims", tags=["claims"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
AdminUserDep = Annotated[User, Depends(require_admin)]
logger = logging.getLogger(__name__)


class PdfLocalIngestRequest(BaseModel):
    file_path: str
    chat_session_id: int | None = None


def _get_claim_or_404(db: Session, claim_id: int, current_user: User) -> Claim:
    claim = db.execute(
        select(Claim).where(Claim.id == claim_id, Claim.doctor_id == current_user.id)
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


def _require_patient(db: Session, patient_id: int, current_user: User) -> Patient:
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.doctor_id == current_user.id)
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


def _require_insurance_company(db: Session, company_id: int) -> InsuranceCompany:
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == company_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=list[ClaimResponse])
def list_claims(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    patient_id: Annotated[int | None, Query()] = None,
    insurance_company_id: Annotated[int | None, Query()] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
) -> list[ClaimResponse]:
    stmt = select(Claim).where(Claim.doctor_id == current_user.id)
    if patient_id:
        stmt = stmt.where(Claim.patient_id == patient_id)
    if insurance_company_id:
        stmt = stmt.where(Claim.insurance_company_id == insurance_company_id)
    if status_value:
        stmt = stmt.where(Claim.claim_status == status_value)
    claims = db.execute(stmt.order_by(Claim.created_at.desc())).scalars().all()
    return [ClaimResponse.model_validate(claim) for claim in claims]


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ClaimCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse | JSONResponse:
    patient = _require_patient(db, payload.patient_id, current_user)
    _require_insurance_company(db, payload.insurance_company_id)
    claim = Claim(
        id=next_id(db, Claim),
        doctor_id=current_user.id,
        patient_id=patient.id,
        insurance_company_id=payload.insurance_company_id,
        claim_number=payload.claim_number,
        claim_status=payload.claim_status,
        service_date=payload.service_date,
        claim_date=payload.claim_date,
        billed_amount_total=payload.billed_amount_total,
        allowed_amount_total=payload.allowed_amount_total,
        coinsurance_amount_total=payload.coinsurance_amount_total,
        copay_amount_total=payload.copay_amount_total,
        deductible_amount_total=payload.deductible_amount_total,
        created_at=utcnow(),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimResponse.model_validate(claim)


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    return ClaimResponse.model_validate(claim)


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: int,
    payload: ClaimUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimResponse | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "patient_id" in data and data["patient_id"] is not None:
        _require_patient(db, data["patient_id"], current_user)
    if "insurance_company_id" in data and data["insurance_company_id"] is not None:
        _require_insurance_company(db, data["insurance_company_id"])
    for field, value in data.items():
        setattr(claim, field, value)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return ClaimResponse.model_validate(claim)


@router.post("/{claim_id}/mcp-codes", response_model=list[ClaimMcpCodeResponse])
def add_mcp_codes(
    claim_id: int,
    payload: ClaimMcpCodeCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ClaimMcpCodeResponse] | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not payload.mcp_codes:
        return []
    codes = db.execute(select(McpCode).where(McpCode.code.in_(payload.mcp_codes))).scalars().all()
    code_by_value = {code.code: code for code in codes}
    missing = [code for code in payload.mcp_codes if code not in code_by_value]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    responses: list[ClaimMcpCodeResponse] = []
    for code_value in payload.mcp_codes:
        existing = db.execute(
            select(ClaimMcpCode).where(
                ClaimMcpCode.claim_id == claim.id,
                ClaimMcpCode.mcp_code == code_value,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="MCP_CODE_ALREADY_LINKED",
                    message="MCP code already linked to claim",
                    details={"mcp_code": code_value},
                ),
            )
        link = ClaimMcpCode(claim_id=claim.id, mcp_code=code_value)
        db.add(link)
        responses.append(ClaimMcpCodeResponse(claim_id=claim.id, mcp_code=code_value))
    db.commit()
    return responses


@router.get("/{claim_id}/policy-links", response_model=list[ClaimPolicyLinkItem])
def resolve_policy_links(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ClaimPolicyLinkItem]:
    claim = _get_claim_or_404(db, claim_id, current_user)
    codes = db.execute(
        select(ClaimMcpCode, McpCode)
        .join(McpCode, ClaimMcpCode.mcp_code == McpCode.code)
        .where(ClaimMcpCode.claim_id == claim.id)
    ).all()
    items: list[ClaimPolicyLinkItem] = []
    for _link, code in codes:
        policy_link = (
            db.execute(
                select(PolicyLink)
                .where(
                    PolicyLink.insurance_company_id == claim.insurance_company_id,
                    PolicyLink.mcp_code == code.code,
                )
                .order_by(PolicyLink.created_at.desc())
            )
            .scalars()
            .first()
        )
        policy_url = policy_link.policy_url if policy_link else None
        items.append(
            ClaimPolicyLinkItem(
                mcp_code=McpCodeSummary(code=code.code, description=code.description),
                policy_url=policy_url,
                missing_policy_link=policy_url is None,
            )
        )
    return items


@router.post("/ingest-pdf", response_model=ClaimPdfIngestResponse)
def ingest_pdf_claim(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
    session_id: int | None = Form(None),
) -> ClaimPdfIngestResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing PDF")

    with tempfile.TemporaryDirectory() as temp_dir:
        safe_name = Path(file.filename).name
        file_path = Path(temp_dir) / safe_name
        with file_path.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        file_size = file_path.stat().st_size
        logger.info(
            "Uploaded PDF filename=%s path=%s size_bytes=%s",
            file.filename,
            file_path,
            file_size,
        )

        parsed = parse_pdf_document(file_path)

    result = ingest_parsed_pdf(
        payload=parsed,
        current_user=current_user,
        db=db,
        session_id=session_id,
    )
    return ClaimPdfIngestResponse.model_validate(result)


@router.post("/ingest-pdf-local")
def ingest_pdf_local(
    payload: PdfLocalIngestRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> dict[str, object]:
    """Local debug endpoint; do not enable in production deployments."""
    file_path = Path(payload.file_path)
    if not file_path.is_absolute():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file_path must be absolute")
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file_path does not exist")
    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file_path must end with .pdf")

    logger.info(
        "Local PDF ingest file_path=%s size_bytes=%s",
        file_path,
        file_path.stat().st_size,
    )

    try:
        parsed = parse_pdf_document(file_path)
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
        "Local PDF parsed parser_mode=%s account_number=%s patient_name=%s service_date=%s cpt_count=%s dx_count=%s",
        os.getenv("PDF_PARSER_MODE", "").strip() or "real",
        user_info.get("account_number"),
        patient_name,
        info[0].get("date") if info else None,
        len(info),
        len(dx_codes),
    )

    result = ingest_parsed_pdf(
        payload=parsed,
        current_user=current_user,
        db=db,
        session_id=payload.chat_session_id,
    )

    # Example:
    # curl -X POST http://127.0.0.1:8000/api/claims/ingest-pdf-local \
    #   -H "Content-Type: application/json" \
    #   -H "Authorization: Bearer <token>" \
    #   -d '{"file_path":"/Users/user/Developer/pythonProject/policy_parser_app/app/api/pdf/parse/test_claim.pdf"}'
    # Verify (psql):
    #   select count(*) from claims;
    #   select count(*) from claim_mcp_codes;
    #   select count(*) from claim_diagnosis_codes;
    return {
        **result,
        "cpt_line_count": result.get("line_count"),
        "dx_code_count": len(dx_codes),
    }
