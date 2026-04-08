"""Chat action confirmation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, CurrentUserDep
from app.core import policy
from app.db.models import ChatSession, Claim, User
from app.db.session import get_db
from app.llm.tools.registry import ToolContext, execute_tool, validate_tool_args
from app.schemas.chat import ChatConfirmRequest, ChatConfirmResponse

router = APIRouter(prefix="/api/chat", tags=["chat_actions"])
DbSessionDep = Annotated[Session, Depends(get_db)]

CONFIRMABLE_TOOLS = {"create_claim_draft", "update_claim_fields"}


@router.post("/confirm-action", response_model=ChatConfirmResponse)
def confirm_chat_action(
    payload: ChatConfirmRequest,
    request: Request,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ChatConfirmResponse:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == payload.session_id,
            *policy.chat_scope_filters(current_user, ChatSession),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    tool_name = payload.tool
    if tool_name not in CONFIRMABLE_TOOLS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported tool")

    entity_id: int | None = None
    if tool_name == "update_claim_fields":
        claim_id = payload.arguments.get("claim_id")
        if isinstance(claim_id, int):
            entity_id = claim_id

    if payload.decision == "reject":
        audit.log_event(
            action="ai_proposal_rejected",
            entity="claim",
            entity_id=entity_id,
            actor=current_user,
            clinic_id=current_user.clinic_id,
            target_clinic_id=current_user.clinic_id,
            diff={"proposal_id": payload.proposal_id, "payload": payload.payload},
            scope="clinic",
            actor_role=current_user.role,
        )
        return ChatConfirmResponse(status="rejected", result=None)

    args = dict(payload.arguments or {})
    args["confirm"] = True
    try:
        validate_tool_args(tool_name, args)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid tool arguments",
        ) from exc

    ctx = ToolContext(
        db=db,
        user_id=current_user.id,
        clinic_id=current_user.clinic_id,
        role=current_user.role,
        chat_session_id=session.id,
        request_id=getattr(request.state, "request_id", None),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    result = execute_tool(tool_name, args, ctx)

    claim_id = None
    if tool_name == "update_claim_fields":
        claim_id = args.get("claim_id")
    elif isinstance(result, dict):
        claim_id = result.get("claim_id")
    if isinstance(claim_id, int):
        entity_id = claim_id
        claim = db.execute(
            select(Claim).where(
                Claim.id == claim_id,
                *policy.claim_scope_filters(current_user, Claim),
            )
        ).scalar_one_or_none()
        if claim is not None:
            session.claim_id = claim.id
            session.patient_id = claim.patient_id
            db.add(session)
            db.commit()

    audit.log_event(
        action="ai_proposal_confirmed",
        entity="claim",
        entity_id=entity_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={"proposal_id": payload.proposal_id, "payload": payload.payload, "result": result},
        scope="clinic",
        actor_role=current_user.role,
    )

    return ChatConfirmResponse(
        status="confirmed", result=result if isinstance(result, dict) else {}
    )
