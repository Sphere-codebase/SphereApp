"""Agent tool endpoints for LLM service."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_agent_token
from app.core.tenancy import apply_rls_context
from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimMcpCode,
    DiagnosisCode,
    McpCode,
    PolicyLink,
    PolicyRule,
    ChatSession,
    User,
)
from app.db.session import get_db
from app.schemas.agent import (
    AgentClaimContextResponse,
    AgentClaimUpdateRequest,
    AgentCodeUpdateRequest,
    AgentPolicyLinkItem,
    AgentPolicyLinksResponse,
    AgentPolicyRuleResponse,
    ClaimRequirementsResponse,
    ClaimValidationResponse,
)
from app.schemas.claims import ClaimDetailResponse, DiagnosisCodeSummary, McpCodeSummary
from app.services.claims.requirements import build_claim_requirements

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(require_agent_token)])
DbSessionDep = Annotated[Session, Depends(get_db)]


def _apply_platform_scope(db: Session) -> None:
    apply_rls_context(db, None, True)


def _apply_clinic_scope(db: Session, clinic_id: int) -> None:
    apply_rls_context(db, clinic_id, False)


def _load_claim(db: Session, claim_id: int) -> Claim:
    _apply_platform_scope(db)
    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    _apply_clinic_scope(db, claim.clinic_id)
    return claim


def _load_session(db: Session, session_id: int) -> ChatSession:
    _apply_platform_scope(db)
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    _apply_clinic_scope(db, session.clinic_id)
    return session


def _require_claim_draft(claim: Claim) -> None:
    if claim.claim_status and claim.claim_status.upper() != "DRAFT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Claim is finalized")


def _resolve_actor(db: Session, user_id: int | None) -> User | None:
    if user_id is None:
        return None
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def _parse_policy_rules(rule: PolicyRule | None) -> tuple[Any | None, Any | None]:
    if rule is None:
        return None, None
    try:
        return rule.extracted_at, rule.rules_json and json.loads(rule.rules_json)
    except Exception:
        return rule.extracted_at, rule.rules_json


def _build_claim_detail(db: Session, claim: Claim) -> ClaimDetailResponse:
    mcp_rows = db.execute(
        select(ClaimMcpCode, McpCode)
        .join(McpCode, ClaimMcpCode.mcp_code == McpCode.code)
        .where(ClaimMcpCode.claim_id == claim.id)
        .order_by(McpCode.code.asc())
    ).all()
    mcp_codes = [McpCodeSummary(code=code.code, description=code.description) for _, code in mcp_rows]

    diagnosis_rows = db.execute(
        select(ClaimDiagnosisCode, DiagnosisCode)
        .join(DiagnosisCode, ClaimDiagnosisCode.diagnosis_code == DiagnosisCode.code)
        .where(ClaimDiagnosisCode.claim_id == claim.id)
        .order_by(DiagnosisCode.code.asc())
    ).all()
    diagnosis_codes = [
        DiagnosisCodeSummary(code=code.code, description=code.description) for _, code in diagnosis_rows
    ]

    status_value = claim.claim_status or "DRAFT"
    if status_value.upper() == "FINAL":
        status_value = "final"
    else:
        status_value = "draft"

    patient = claim.patient
    return ClaimDetailResponse(
        id=claim.id,
        claim_status=status_value,
        updated_at=claim.updated_at,
        patient={
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
        },
        insurance_company_id=claim.insurance_company_id,
        service_date=claim.service_date,
        mcp_codes=mcp_codes,
        diagnosis_codes=diagnosis_codes,
    )


@router.get("/claim-context", response_model=AgentClaimContextResponse)
def get_claim_context(
    db: DbSessionDep,
    session_id: Annotated[int, Query()],
) -> AgentClaimContextResponse:
    session = _load_session(db, session_id)
    if session.claim_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not attached")
    claim = db.execute(select(Claim).where(Claim.id == session.claim_id)).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    claim_detail = _build_claim_detail(db, claim)

    _, policy_links, policy_rules = build_claim_requirements(db, claim)
    policy_rules_response = [
        AgentPolicyRuleResponse(
            policy_link_id=item.policy_link_id,
            extracted_at=item.extracted_at,
            rules_json=item.rules_json,
        )
        for item in policy_rules
    ]

    return AgentClaimContextResponse(
        claim=claim_detail,
        procedures=claim_detail.mcp_codes,
        diagnoses=claim_detail.diagnosis_codes,
        policy_links=[
            AgentPolicyLinkItem(
                mcp_code=link.mcp_code,
                policy_link_id=link.id,
                policy_url=link.policy_url,
            )
            for link in policy_links
        ],
        policy_rules=policy_rules_response,
    )


@router.patch("/claims/{claim_id}")
def update_claim(
    claim_id: int,
    payload: AgentClaimUpdateRequest,
    db: DbSessionDep,
    audit: AuditLoggerDep,
):
    claim = _load_claim(db, claim_id)
    _require_claim_draft(claim)

    updates = payload.set or {}
    patient_updates = payload.patient_set or {}

    allowed_claim_fields = {
        "service_date",
        "insurance_company_id",
        "claim_number",
        "claim_date",
        "billed_amount_total",
        "allowed_amount_total",
        "coinsurance_amount_total",
        "copay_amount_total",
        "deductible_amount_total",
    }
    for field, value in updates.items():
        if field in allowed_claim_fields:
            setattr(claim, field, value)

    if patient_updates:
        patient = claim.patient
        allowed_patient_fields = {"first_name", "last_name", "date_of_birth"}
        for field, value in patient_updates.items():
            if field in allowed_patient_fields:
                setattr(patient, field, value)
        db.add(patient)

    db.add(claim)
    db.commit()
    db.refresh(claim)

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.claim_updated",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={
            "tool_name": "agent.update_claim",
            "payload": payload.model_dump(exclude_unset=True),
        },
    )

    return {"status": "ok"}


@router.post("/claims/{claim_id}/mcp-codes")
def add_mcp_code(
    claim_id: int,
    payload: AgentCodeUpdateRequest,
    db: DbSessionDep,
    audit: AuditLoggerDep,
):
    claim = _load_claim(db, claim_id)
    _require_claim_draft(claim)
    code = db.execute(select(McpCode).where(McpCode.code == payload.code)).scalar_one_or_none()
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    existing = db.execute(
        select(ClaimMcpCode).where(
            ClaimMcpCode.claim_id == claim.id,
            ClaimMcpCode.mcp_code == payload.code,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP code already linked")
    db.add(ClaimMcpCode(claim_id=claim.id, mcp_code=payload.code))
    db.commit()

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.added_mcp",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"tool_name": "agent.add_mcp", "payload": {"code": payload.code}},
    )
    return {"status": "ok"}


@router.delete("/claims/{claim_id}/mcp-codes/{code}")
def remove_mcp_code(
    claim_id: int,
    code: str,
    db: DbSessionDep,
    audit: AuditLoggerDep,
):
    claim = _load_claim(db, claim_id)
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

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.removed_mcp",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"tool_name": "agent.remove_mcp", "payload": {"code": code}},
    )
    return {"status": "ok"}


@router.post("/claims/{claim_id}/diagnosis-codes")
def add_diagnosis_code(
    claim_id: int,
    payload: AgentCodeUpdateRequest,
    db: DbSessionDep,
    audit: AuditLoggerDep,
):
    claim = _load_claim(db, claim_id)
    _require_claim_draft(claim)
    code = (
        db.execute(select(DiagnosisCode).where(DiagnosisCode.code == payload.code))
        .scalar_one_or_none()
    )
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not found")
    existing = db.execute(
        select(ClaimDiagnosisCode).where(
            ClaimDiagnosisCode.claim_id == claim.id,
            ClaimDiagnosisCode.diagnosis_code == payload.code,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Diagnosis code already linked")
    db.add(ClaimDiagnosisCode(claim_id=claim.id, diagnosis_code=payload.code))
    db.commit()

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.added_diagnosis",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"tool_name": "agent.add_diagnosis", "payload": {"code": payload.code}},
    )
    return {"status": "ok"}


@router.delete("/claims/{claim_id}/diagnosis-codes/{code}")
def remove_diagnosis_code(
    claim_id: int,
    code: str,
    db: DbSessionDep,
    audit: AuditLoggerDep,
):
    claim = _load_claim(db, claim_id)
    _require_claim_draft(claim)
    link = db.execute(
        select(ClaimDiagnosisCode).where(
            ClaimDiagnosisCode.claim_id == claim.id,
            ClaimDiagnosisCode.diagnosis_code == code,
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not linked")
    db.delete(link)
    db.commit()

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.removed_diagnosis",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={"tool_name": "agent.remove_diagnosis", "payload": {"code": code}},
    )
    return {"status": "ok"}


@router.get("/policy-links", response_model=AgentPolicyLinksResponse)
def list_policy_links(
    db: DbSessionDep,
    insurance_company_id: Annotated[int, Query()],
    mcp_code: Annotated[str, Query()],
) -> AgentPolicyLinksResponse:
    _apply_platform_scope(db)
    links = (
        db.execute(
            select(PolicyLink).where(
                PolicyLink.insurance_company_id == insurance_company_id,
                PolicyLink.mcp_code == mcp_code,
            )
        )
        .scalars()
        .all()
    )
    return AgentPolicyLinksResponse(
        items=[
            AgentPolicyLinkItem(
                mcp_code=link.mcp_code,
                policy_link_id=link.id,
                policy_url=link.policy_url,
            )
            for link in links
        ]
    )


@router.get("/policy-rules/{policy_link_id}/latest", response_model=AgentPolicyRuleResponse)
def get_policy_rules_latest(
    policy_link_id: int,
    db: DbSessionDep,
) -> AgentPolicyRuleResponse:
    _apply_platform_scope(db)
    rule = (
        db.execute(
            select(PolicyRule)
            .where(PolicyRule.policy_link_id == policy_link_id)
            .order_by(PolicyRule.extracted_at.desc())
        )
        .scalars()
        .first()
    )
    extracted_at, rules_json = _parse_policy_rules(rule)
    return AgentPolicyRuleResponse(
        policy_link_id=policy_link_id,
        extracted_at=extracted_at,
        rules_json=rules_json,
    )


@router.post("/claims/{claim_id}/requirements", response_model=ClaimRequirementsResponse)
def check_claim_requirements(
    claim_id: int,
    db: DbSessionDep,
    audit: AuditLoggerDep,
) -> ClaimRequirementsResponse:
    claim = _load_claim(db, claim_id)
    requirements, _, _ = build_claim_requirements(db, claim)

    actor = _resolve_actor(db, claim.doctor_id)
    audit.log_event(
        action="ai.requirements_checked",
        entity="claim",
        entity_id=claim.id,
        actor=actor,
        clinic_id=claim.clinic_id,
        target_clinic_id=claim.clinic_id,
        diff={
            "tool_name": "agent.check_requirements",
            "payload": {"missing": [item["key"] for item in requirements["missing"]]},
        },
    )
    if requirements["missing"]:
        audit.log_event(
            action="ai.prompted_missing_field",
            entity="claim",
            entity_id=claim.id,
            actor=actor,
            clinic_id=claim.clinic_id,
            target_clinic_id=claim.clinic_id,
            diff={
                "tool_name": "agent.prompt_missing",
                "payload": {"missing": requirements["missing"]},
            },
        )

    return ClaimRequirementsResponse(**requirements)


@router.post("/claims/{claim_id}/validate", response_model=ClaimValidationResponse)
def validate_claim(
    claim_id: int,
    db: DbSessionDep,
) -> ClaimValidationResponse:
    claim = _load_claim(db, claim_id)
    requirements, _, _ = build_claim_requirements(db, claim)
    warnings = [
        field["key"]
        for field in requirements["required_fields"]
        if field.get("severity") == "recommended"
    ]
    return ClaimValidationResponse(
        is_complete=requirements["is_complete"],
        missing=[{"key": item["key"], "question": item["question"]} for item in requirements["missing"]],
        warnings=warnings,
    )
