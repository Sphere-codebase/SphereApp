"""Chat session JSON endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep
from app.core import policy
from app.core.security import get_current_user
from app.db.id_utils import next_id
from app.db.models import AuditLog, ChatMessage, ChatSession, Claim, User
from app.db.session import get_db
from app.schemas.chat_sessions import (
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[ChatSessionResponse])
def list_sessions(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ChatSessionResponse]:
    sessions = (
        db.execute(
            select(ChatSession)
            .where(*policy.chat_scope_filters(current_user, ChatSession))
            .order_by(ChatSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [ChatSessionResponse.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ChatSessionResponse:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            *policy.chat_scope_filters(current_user, ChatSession),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return ChatSessionResponse.model_validate(session)


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ChatSessionResponse:
    claim = None
    if payload.claim_id is not None:
        claim = db.execute(
            select(Claim).where(
                Claim.id == payload.claim_id,
                *policy.claim_scope_filters(current_user, Claim),
            )
        ).scalar_one_or_none()
        if claim is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    session = ChatSession(
        id=next_id(db, ChatSession),
        doctor_id=current_user.id,
        clinic_id=current_user.clinic_id,
        title=payload.title,
        claim_id=claim.id if claim else None,
        patient_id=claim.patient_id if claim else None,
        created_at=utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    created_fields: list[str] = []
    if payload.title:
        created_fields.append("title")
    if claim is not None:
        created_fields.extend(["claim_id", "patient_id"])
    audit.log_event(
        action="CREATE",
        entity="chat_session",
        entity_id=session.id,
        actor=current_user,
        clinic_id=session.clinic_id,
        target_clinic_id=session.clinic_id,
        diff={"fields": created_fields},
    )
    return ChatSessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: int,
    payload: ChatSessionUpdateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ChatSessionResponse:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            *policy.chat_scope_filters(current_user, ChatSession),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    updated_fields: list[str] = []
    if payload.title is not None:
        session.title = payload.title
        updated_fields.append("title")
    if payload.claim_id is not None:
        claim = db.execute(
            select(Claim).where(
                Claim.id == payload.claim_id,
                *policy.claim_scope_filters(current_user, Claim),
            )
        ).scalar_one_or_none()
        if claim is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        session.claim_id = claim.id
        session.patient_id = claim.patient_id
        updated_fields.append("claim_id")
        updated_fields.append("patient_id")

    if updated_fields:
        db.add(session)
        db.commit()
        db.refresh(session)
        audit.log_event(
            action="UPDATE",
            entity="chat_session",
            entity_id=session.id,
            actor=current_user,
            clinic_id=session.clinic_id,
            target_clinic_id=session.clinic_id,
            diff={"fields": updated_fields},
        )
    return ChatSessionResponse.model_validate(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_session(
    session_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            *policy.chat_scope_filters(current_user, ChatSession),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.execute(
        AuditLog.__table__.delete().where(
            AuditLog.entity == "chat_session",
            AuditLog.entity_id == str(session.id),
        )
    )
    db.execute(ChatMessage.__table__.delete().where(ChatMessage.session_id == session.id))
    db.delete(session)
    db.commit()
    audit.log_event(
        action="DELETE",
        entity="chat_session",
        entity_id=session.id,
        actor=current_user,
        clinic_id=session.clinic_id,
        target_clinic_id=session.clinic_id,
        diff={"audit_pruned": True},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    session_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ChatMessageResponse]:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            *policy.chat_scope_filters(current_user, ChatSession),
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = (
        db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.clinic_id == current_user.clinic_id,
                ChatMessage.role.in_(["user", "assistant"]),
            )
            .order_by(ChatMessage.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [ChatMessageResponse.model_validate(message) for message in messages]
