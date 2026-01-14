"""Chat session JSON endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import ChatMessage, ChatSession, Claim, Patient, User
from app.db.session import get_db
from app.schemas.chat_sessions import (
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
)

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[ChatSessionResponse])
def list_sessions(db: DbSessionDep, current_user: CurrentUserDep) -> list[ChatSessionResponse]:
    sessions = (
        db.execute(
            select(ChatSession)
            .where(
                ChatSession.tenant_id == current_user.tenant_id,
                ChatSession.user_id == current_user.id,
            )
            .order_by(ChatSession.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ChatSessionResponse.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ChatSessionResponse:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == current_user.tenant_id,
            ChatSession.user_id == current_user.id,
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
) -> ChatSessionResponse:
    if payload.claim_id:
        claim = db.execute(
            select(Claim)
            .join(Patient)
            .where(
                Claim.id == payload.claim_id,
                Claim.tenant_id == current_user.tenant_id,
                Patient.id == Claim.patient_id,
                Patient.user_id == current_user.id,
            )
        ).scalar_one_or_none()
        if claim is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    session = ChatSession(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        claim_id=payload.claim_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionResponse.model_validate(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_session(
    session_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> Response:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == current_user.tenant_id,
            ChatSession.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.delete(session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    session_id: uuid.UUID,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> list[ChatMessageResponse]:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == current_user.tenant_id,
            ChatSession.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = (
        db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.tenant_id == current_user.tenant_id,
                ChatMessage.role.in_(["user", "assistant"]),
            )
            .order_by(ChatMessage.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [ChatMessageResponse.model_validate(message) for message in messages]
