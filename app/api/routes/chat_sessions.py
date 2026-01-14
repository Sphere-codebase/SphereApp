"""Chat session JSON endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import ChatSession, Claim, User
from app.db.session import get_db
from app.schemas.chat_sessions import ChatSessionCreateRequest, ChatSessionResponse

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


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreateRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ChatSessionResponse:
    if payload.claim_id:
        claim = db.execute(
            select(Claim).where(
                Claim.id == payload.claim_id,
                Claim.tenant_id == current_user.tenant_id,
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
