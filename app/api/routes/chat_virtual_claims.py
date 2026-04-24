"""Session-scoped virtual claim checklist endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AuditLoggerDep, CurrentUserDep, DbSessionDep
from app.schemas.virtual_claims import (
    VirtualClaimBootstrapRequest,
    VirtualClaimMaterializeRequest,
    VirtualClaimMaterializeResponse,
    VirtualClaimPatchRequest,
    VirtualClaimResponse,
)
from app.services.claims.virtual_claims import (
    bootstrap_virtual_claim_context,
    ensure_virtual_claim_draft,
    get_virtual_claim_state,
    get_scoped_chat_session,
    materialize_virtual_claim,
    recompute_virtual_claim,
    update_virtual_claim_state,
)

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_virtual_claims"])


@router.post("/{session_id}/virtual-claim", response_model=VirtualClaimResponse)
def ensure_virtual_claim(
    session_id: int,
    payload: VirtualClaimBootstrapRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> VirtualClaimResponse:
    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
    )
    return bootstrap_virtual_claim_context(
        db,
        session,
        patient_id=payload.patient_id,
        insurance_company_id=payload.insurance_company_id,
        procedure_code=payload.procedure_code,
    )


@router.get("/{session_id}/virtual-claim", response_model=VirtualClaimResponse)
def get_virtual_claim(
    session_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> VirtualClaimResponse:
    response = get_virtual_claim_state(
        db,
        session_id=session_id,
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
        create_if_missing=False,
    )
    if response is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Virtual claim not found")
    return response


@router.patch("/{session_id}/virtual-claim", response_model=VirtualClaimResponse)
def patch_virtual_claim(
    session_id: int,
    payload: VirtualClaimPatchRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> VirtualClaimResponse:
    return update_virtual_claim_state(
        db,
        session_id=session_id,
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
        patch={
            "patient_id": payload.patient_id,
            "insurance_company_id": payload.insurance_company_id,
            "procedure_code": payload.procedure_code,
            "fields": [field.model_dump(mode="json") for field in payload.fields],
        },
        source_type=payload.source_type,
    )


@router.post("/{session_id}/virtual-claim/recompute", response_model=VirtualClaimResponse)
def recompute_virtual_claim_route(
    session_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> VirtualClaimResponse:
    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
    )
    draft = ensure_virtual_claim_draft(db, session)
    return recompute_virtual_claim(db, draft)


@router.post(
    "/{session_id}/virtual-claim/materialize",
    response_model=VirtualClaimMaterializeResponse,
)
def materialize_virtual_claim_route(
    session_id: int,
    payload: VirtualClaimMaterializeRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> VirtualClaimMaterializeResponse:
    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
    )
    draft = ensure_virtual_claim_draft(db, session)
    result = materialize_virtual_claim(db, session=session, draft=draft, confirm=payload.confirm)
    audit.log_event(
        action="AI_WRITE_CONFIRMED" if payload.confirm else "AI_WRITE_PROPOSED",
        entity="virtual_claim_draft",
        entity_id=draft.id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={
            "tool": "materialize_virtual_claim_route",
            "confirm": payload.confirm,
            "claim_id": result.claim_id,
        },
    )
    return result
