"""Claim endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_platform_staff_admin
from app.core import policy
from app.core.logging import error_payload
from app.core.security import get_current_user
from app.db.id_utils import next_id
from app.db.models import (
    ChatSession,
    Claim,
    ClaimDiagnosisCode,
    ClaimMcpCode,
    ClaimPDF,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    McpPaymentPrediction,
    MlPrediction,
    Patient,
    PolicyLink,
    User,
)
from app.db.session import get_db
from app.pdf.claim_pdf import generate_pdf_bytes
from app.repositories import patients as patient_repo
from app.schemas.agent import ClaimRequirementsResponse
from app.schemas.claims import (
    ClaimCreateRequest,
    ClaimDetailResponse,
    ClaimDiagnosisCodeCreateRequest,
    ClaimDiagnosisCodeResponse,
    ClaimFinancialFlag,
    ClaimFinancialPrediction,
    ClaimFinancialSummary,
    ClaimMcpCodeCreateRequest,
    ClaimMcpCodeResponse,
    ClaimPdfIngestResponse,
    ClaimPolicyLinkItem,
    ClaimResponse,
    ClaimSummaryListResponse,
    ClaimUpdateRequest,
    DiagnosisCodeSummary,
    McpCodeSummary,
    MyClaimsListResponseSchema,
    PatientSummary,
)
from app.services.claims.ingestion import ingest_pdf_from_path, ingest_pdf_from_upload
from app.services.claims.pdf import build_claim_pdf_data
from app.services.claims.requirements import build_claim_requirements
from app.services.claims.summary import ClaimsService, MyClaimsFilters
from app.utils.time import utcnow

router = APIRouter(prefix="/api/claims", tags=["claims"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]

logger = logging.getLogger(__name__)


class PdfLocalIngestRequest(BaseModel):
    file_path: str
    chat_session_id: int | None = None


def _get_claim_or_404(db: Session, claim_id: int, current_user: User) -> Claim:
    filters = [Claim.id == claim_id]
    filters.extend(policy.claim_scope_filters(current_user, Claim))
    claim = db.execute(select(Claim).where(*filters)).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


def _get_claim_unscoped_or_404(db: Session, claim_id: int) -> Claim:
    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


def _require_patient(db: Session, patient_id: int, current_user: User) -> Patient:
    filters = [Patient.id == patient_id]
    filters.extend(policy.patient_scope_filters(current_user, Patient))
    patient = db.execute(select(Patient).where(*filters)).scalar_one_or_none()
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


def _require_claim_draft(claim: Claim) -> None:
    if claim.claim_status and claim.claim_status.upper() != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim is finalized",
        )


def _build_claim_detail(db: Session, claim: Claim) -> ClaimDetailResponse:
    status_value = claim.claim_status or "DRAFT"
    if status_value.upper() == "FINAL":
        status_value = "final"
    mcp_rows = db.execute(
        select(ClaimMcpCode, McpCode)
        .join(McpCode, ClaimMcpCode.mcp_code == McpCode.code)
        .where(ClaimMcpCode.claim_id == claim.id)
        .order_by(McpCode.code.asc())
    ).all()
    mcp_codes = [
        McpCodeSummary(code=code.code, description=code.description) for _link, code in mcp_rows
    ]

    diagnosis_rows = db.execute(
        select(ClaimDiagnosisCode, DiagnosisCode)
        .join(DiagnosisCode, ClaimDiagnosisCode.diagnosis_code == DiagnosisCode.code)
        .where(ClaimDiagnosisCode.claim_id == claim.id)
        .order_by(DiagnosisCode.code.asc())
    ).all()
    diagnosis_codes = [
        DiagnosisCodeSummary(code=code.code, description=code.description)
        for _link, code in diagnosis_rows
    ]

    patient = claim.patient
    return ClaimDetailResponse(
        id=claim.id,
        claim_status=status_value,
        updated_at=claim.updated_at,
        patient=PatientSummary(
            id=patient.id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
        ),
        insurance_company_id=claim.insurance_company_id,
        service_date=claim.service_date,
        mcp_codes=mcp_codes,
        diagnosis_codes=diagnosis_codes,
    )


def _pdf_filename(claim_id: int) -> tuple[str, str]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pdf_id = f"claim_{claim_id}_{timestamp}"
    filename = f"{pdf_id}.pdf"
    return pdf_id, filename


def _build_claim_financial_summary(db: Session, claim: Claim) -> ClaimFinancialSummary:
    mcp_codes = (
        db.execute(
            select(ClaimMcpCode.mcp_code)
            .where(ClaimMcpCode.claim_id == claim.id)
            .order_by(ClaimMcpCode.mcp_code.asc())
        )
        .scalars()
        .all()
    )
    diagnosis_codes = (
        db.execute(
            select(ClaimDiagnosisCode.diagnosis_code).where(ClaimDiagnosisCode.claim_id == claim.id)
        )
        .scalars()
        .all()
    )

    predictions: list[ClaimFinancialPrediction] = []
    flags: list[ClaimFinancialFlag] = []

    if not diagnosis_codes:
        flags.append(
            ClaimFinancialFlag(
                code="missing_diagnosis",
                severity="warn",
                message="No diagnosis codes attached to this claim.",
            )
        )

    payment_map: dict[str, McpPaymentPrediction] = {}
    ml_map: dict[str, MlPrediction] = {}

    if mcp_codes:
        today = date.today()
        payment_rows = (
            db.execute(
                select(McpPaymentPrediction)
                .where(
                    McpPaymentPrediction.insurance_company_id == claim.insurance_company_id,
                    McpPaymentPrediction.mcp_code.in_(mcp_codes),
                    McpPaymentPrediction.prediction_date <= today,
                )
                .order_by(
                    McpPaymentPrediction.mcp_code.asc(),
                    McpPaymentPrediction.prediction_date.desc(),
                )
            )
            .scalars()
            .all()
        )
        for row in payment_rows:
            if row.mcp_code not in payment_map:
                payment_map[row.mcp_code] = row

        ml_rows = (
            db.execute(
                select(MlPrediction)
                .where(
                    MlPrediction.claim_id == claim.id,
                    MlPrediction.insurance_company_id == claim.insurance_company_id,
                    MlPrediction.mcp_code.in_(mcp_codes),
                )
                .order_by(MlPrediction.mcp_code.asc(), MlPrediction.created_at.desc())
            )
            .scalars()
            .all()
        )
        for row in ml_rows:
            if row.mcp_code not in ml_map:
                ml_map[row.mcp_code] = row

    for code in mcp_codes:
        if code in payment_map:
            row = payment_map[code]
            predicted_amount = float(row.predicted_paid_amount)
            predictions.append(
                ClaimFinancialPrediction(
                    mcp_code=code,
                    predicted_paid_amount=predicted_amount,
                    confidence=row.confidence,
                    explanation=None,
                    source="mcp_payment_predictions",
                )
            )
            if row.confidence is not None and row.confidence < 0.5:
                severity = "high" if row.confidence < 0.3 else "warn"
                flags.append(
                    ClaimFinancialFlag(
                        code=f"low_confidence:{code}",
                        severity=severity,
                        message=f"Low confidence prediction for {code}.",
                    )
                )
            continue

        if code in ml_map:
            row = ml_map[code]
            predictions.append(
                ClaimFinancialPrediction(
                    mcp_code=code,
                    predicted_paid_amount=0.0,
                    confidence=row.confidence,
                    explanation=row.explanation,
                    source="ml_predictions",
                )
            )
            if row.confidence is not None and row.confidence < 0.5:
                severity = "high" if row.confidence < 0.3 else "warn"
                flags.append(
                    ClaimFinancialFlag(
                        code=f"low_confidence:{code}",
                        severity=severity,
                        message=f"Low confidence prediction for {code}.",
                    )
                )
            continue

        predictions.append(
            ClaimFinancialPrediction(
                mcp_code=code,
                predicted_paid_amount=0.0,
                confidence=None,
                explanation="No prediction found.",
                source="ml_predictions",
            )
        )
        flags.append(
            ClaimFinancialFlag(
                code=f"missing_prediction:{code}",
                severity="warn",
                message=f"No prediction available for {code}.",
            )
        )

    predicted_total = sum(item.predicted_paid_amount for item in predictions)

    return ClaimFinancialSummary(
        claim_id=claim.id,
        currency="USD",
        predicted_total_paid_amount=predicted_total,
        predicted_per_mcp=predictions,
        flags=flags,
        updated_at=utcnow(),
    )


@router.get("", response_model=list[ClaimResponse])
def list_claims(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    patient_id: Annotated[int | None, Query()] = None,
    insurance_company_id: Annotated[int | None, Query()] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
) -> list[ClaimResponse]:
    stmt = select(Claim).where(*policy.claim_scope_filters(current_user, Claim))
    if patient_id:
        stmt = stmt.where(Claim.patient_id == patient_id)
    if insurance_company_id:
        stmt = stmt.where(Claim.insurance_company_id == insurance_company_id)
    if status_value:
        stmt = stmt.where(Claim.claim_status == status_value)
    claims = db.execute(stmt.order_by(Claim.created_at.desc())).scalars().all()
    return [ClaimResponse.model_validate(claim) for claim in claims]


@router.get("/my", response_model=MyClaimsListResponseSchema)
def list_my_claims(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> MyClaimsListResponseSchema:
    service = ClaimsService(db)
    filters = MyClaimsFilters(
        limit=limit,
        offset=offset,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
    return service.list_my_claims_summary(current_user=current_user, filters=filters)


@router.get("/my-summary", response_model=ClaimSummaryListResponse)
def list_my_claims_summary(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> ClaimSummaryListResponse:
    service = ClaimsService(db)
    filters = MyClaimsFilters(
        limit=limit,
        offset=offset,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
    summary = service.list_my_claims_summary(current_user=current_user, filters=filters)
    return ClaimSummaryListResponse.model_validate(summary.model_dump())


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ClaimCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ClaimResponse | JSONResponse:
    if not policy.can(current_user, policy.Action.CREATE, policy.Resource.CLAIM):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    chat_session: ChatSession | None = None
    if payload.session_id is not None:
        chat_session = db.execute(
            select(ChatSession).where(
                ChatSession.id == payload.session_id,
                *policy.chat_scope_filters(current_user, ChatSession),
            )
        ).scalar_one_or_none()
        if chat_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found",
            )
    if payload.patient_id is not None:
        patient = _require_patient(db, payload.patient_id, current_user)
    elif payload.patient is not None:
        patient = patient_repo.upsert_patient(
            db,
            doctor_id=current_user.id,
            clinic_id=current_user.clinic_id,
            first_name=payload.patient.first_name,
            last_name=payload.patient.last_name,
            date_of_birth=payload.patient.date_of_birth,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="patient_id or patient is required",
        )
    _require_insurance_company(db, payload.insurance_company_id)
    claim = Claim(
        id=next_id(db, Claim),
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
        patient_id=patient.id,
        insurance_company_id=payload.insurance_company_id,
        claim_number=payload.claim_number,
        claim_status=payload.claim_status or "DRAFT",
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
    if chat_session is not None:
        chat_session.claim_id = claim.id
        chat_session.patient_id = patient.id
        db.add(chat_session)
        db.commit()
    audit.log_event(
        action="CREATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={
            "fields": list(payload.model_dump(exclude_unset=True).keys()),
            "patient_id": claim.patient_id,
            "insurance_company_id": claim.insurance_company_id,
        },
    )
    return ClaimResponse.model_validate(claim)


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
def get_claim(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimDetailResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    return _build_claim_detail(db, claim)


@router.post("/{claim_id}/requirements", response_model=ClaimRequirementsResponse)
def get_claim_requirements(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimRequirementsResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    requirements, _, _ = build_claim_requirements(db, claim)
    return ClaimRequirementsResponse(**requirements)


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: int,
    payload: ClaimUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ClaimResponse | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
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
    audit.log_event(
        action="UPDATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"fields": list(data.keys())},
    )
    return ClaimResponse.model_validate(claim)


@router.post("/{claim_id}/mcp-codes", response_model=list[ClaimMcpCodeResponse])
def add_mcp_codes(
    claim_id: int,
    payload: ClaimMcpCodeCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> list[ClaimMcpCodeResponse] | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _require_claim_draft(claim)
    codes_to_add = payload.mcp_codes
    if payload.code:
        codes_to_add = [payload.code] + codes_to_add
    if not codes_to_add:
        return []
    codes = db.execute(select(McpCode).where(McpCode.code.in_(codes_to_add))).scalars().all()
    code_by_value = {code.code: code for code in codes}
    missing = [code for code in codes_to_add if code not in code_by_value]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    responses: list[ClaimMcpCodeResponse] = []
    for code_value in codes_to_add:
        existing = db.execute(
            select(ClaimMcpCode).where(
                ClaimMcpCode.claim_id == claim.id,
                ClaimMcpCode.mcp_code == code_value,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
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
    audit.log_event(
        action="UPDATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"mcp_codes": codes_to_add},
    )
    return responses


@router.delete("/{claim_id}/mcp-codes/{code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mcp_code(
    claim_id: int,
    code: str,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _require_claim_draft(claim)
    link = db.execute(
        select(ClaimMcpCode).where(
            ClaimMcpCode.claim_id == claim.id,
            ClaimMcpCode.mcp_code == code,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not linked")
    db.delete(link)
    db.commit()
    audit.log_event(
        action="UPDATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"removed_mcp_code": code},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{claim_id}/diagnosis-codes", response_model=list[ClaimDiagnosisCodeResponse])
def add_diagnosis_codes(
    claim_id: int,
    payload: ClaimDiagnosisCodeCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> list[ClaimDiagnosisCodeResponse] | JSONResponse:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _require_claim_draft(claim)
    codes_to_add = payload.diagnosis_codes
    if payload.code:
        codes_to_add = [payload.code] + codes_to_add
    if not codes_to_add:
        return []
    codes = (
        db.execute(select(DiagnosisCode).where(DiagnosisCode.code.in_(codes_to_add)))
        .scalars()
        .all()
    )
    code_by_value = {code.code: code for code in codes}
    missing = [code for code in codes_to_add if code not in code_by_value]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not found"
        )
    responses: list[ClaimDiagnosisCodeResponse] = []
    for code_value in codes_to_add:
        existing = db.execute(
            select(ClaimDiagnosisCode).where(
                ClaimDiagnosisCode.claim_id == claim.id,
                ClaimDiagnosisCode.diagnosis_code == code_value,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_payload(
                    code="DIAGNOSIS_CODE_ALREADY_LINKED",
                    message="Diagnosis code already linked to claim",
                    details={"diagnosis_code": code_value},
                ),
            )
        link = ClaimDiagnosisCode(claim_id=claim.id, diagnosis_code=code_value)
        db.add(link)
        responses.append(ClaimDiagnosisCodeResponse(claim_id=claim.id, diagnosis_code=code_value))
    db.commit()
    audit.log_event(
        action="UPDATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"diagnosis_codes": codes_to_add},
    )
    return responses


@router.delete("/{claim_id}/diagnosis-codes/{code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_diagnosis_code(
    claim_id: int,
    code: str,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _require_claim_draft(claim)
    link = db.execute(
        select(ClaimDiagnosisCode).where(
            ClaimDiagnosisCode.claim_id == claim.id,
            ClaimDiagnosisCode.diagnosis_code == code,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not linked"
        )
    db.delete(link)
    db.commit()
    audit.log_event(
        action="UPDATE",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"removed_diagnosis_code": code},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{claim_id}/finalize", response_model=ClaimDetailResponse)
def finalize_claim(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ClaimDetailResponse:
    claim = _get_claim_unscoped_or_404(db, claim_id)
    if not policy.can(current_user, policy.Action.UPDATE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if claim.claim_status and claim.claim_status.lower() == "final":
        return _build_claim_detail(db, claim)
    claim.claim_status = "FINAL"
    claim.updated_at = utcnow()
    db.add(claim)
    db.commit()
    db.refresh(claim)
    audit.log_event(
        action="claim.finalized",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"from": "draft", "to": "final"},
        scope="clinic",
        actor_role=current_user.role,
    )
    return _build_claim_detail(db, claim)


@router.post("/{claim_id}/pdf")
def generate_claim_pdf(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> dict[str, str]:
    claim = _get_claim_unscoped_or_404(db, claim_id)
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    claim_data = build_claim_pdf_data(db, claim)
    try:
        pdf_bytes = generate_pdf_bytes(claim_data)
        pdf_id, filename = _pdf_filename(claim.id)
    except Exception as exc:
        logger.exception("Failed to generate PDF for claim %s", claim.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF",
        ) from exc

    record = ClaimPDF(
        clinic_id=claim.clinic_id,
        claim_id=claim.id,
        storage_key=filename,
        version=1,
        created_by=current_user.id,
    )
    db.add(record)
    db.commit()
    audit.log_event(
        action="claim.pdf_generated",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"pdf_id": pdf_id, "filename": filename, "bytes": len(pdf_bytes)},
        scope="clinic",
        actor_role=current_user.role,
    )
    return {"pdf_id": pdf_id, "pdf_url": f"/api/files/pdfs/{filename}"}


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


@router.get("/{claim_id}/financial", response_model=ClaimFinancialSummary)
def get_claim_financial(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClaimFinancialSummary:
    claim = _get_claim_unscoped_or_404(db, claim_id)
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return _build_claim_financial_summary(db, claim)


@router.post("/{claim_id}/financial/refresh", response_model=ClaimFinancialSummary)
def refresh_claim_financial(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ClaimFinancialSummary:
    claim = _get_claim_unscoped_or_404(db, claim_id)
    if not policy.can(current_user, policy.Action.READ, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    summary = _build_claim_financial_summary(db, claim)
    audit.log_event(
        action="claim.financial_refreshed",
        entity="claim",
        entity_id=claim.id,
        actor=current_user,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"reason": "user_clicked_refresh"},
        scope="clinic",
        actor_role=current_user.role,
    )
    return summary


@router.post("/ingest-pdf", response_model=ClaimPdfIngestResponse)
def ingest_pdf_claim(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
    file: UploadFile = File(...),  # noqa: B008
    session_id: int | None = Form(None),  # noqa: B008
) -> ClaimPdfIngestResponse:
    if not policy.can(current_user, policy.Action.CREATE, policy.Resource.CLAIM):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = ingest_pdf_from_upload(
        file=file,
        current_user=current_user,
        db=db,
        session_id=session_id,
        audit_logger=audit,
    )
    return ClaimPdfIngestResponse.model_validate(result)


@router.post("/ingest-pdf-local")
def ingest_pdf_local(
    payload: PdfLocalIngestRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> dict[str, object]:
    """Local debug endpoint; do not enable in production deployments."""
    result = ingest_pdf_from_path(
        file_path=payload.file_path,
        current_user=current_user,
        db=db,
        session_id=payload.chat_session_id,
        audit_logger=audit,
    )
    return result


@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_claim(
    claim_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    claim = _get_claim_or_404(db, claim_id, current_user)
    if not policy.can(current_user, policy.Action.DELETE, policy.Resource.CLAIM, claim):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    claim_id_value = claim.id
    clinic_id_value = claim.clinic_id
    db.delete(claim)
    db.commit()
    audit.log_event(
        action="DELETE",
        entity="claim",
        entity_id=claim_id_value,
        actor=current_user,
        clinic_id=clinic_id_value,
        target_clinic_id=clinic_id_value,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
