"""Chat routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.llm.client import LLMClient
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_orchestrator import ChatOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_llm_client() -> LLMClient:
    return LLMClient()


LlmClientDep = Annotated[LLMClient, Depends(get_llm_client)]


def get_chat_orchestrator(
    db: DbSessionDep, current_user: CurrentUserDep, llm_client: LlmClientDep
) -> ChatOrchestrator:
    return ChatOrchestrator(db=db, user=current_user, llm_client=llm_client)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> ChatResponse:
    result = orchestrator.run(
        message=payload.message,
        session_id=payload.session_id,
        claim_id=payload.claim_id,
    )
    if settings.env in {"dev", "test"}:
        tool_steps = result.debug["tool_steps"] if result.debug else 0
        logger.info(
            "chat completed session_id=%s tool_steps=%s",
            result.session_id,
            tool_steps,
        )

    return ChatResponse(
        session_id=result.session_id,
        assistant_message=result.assistant_message,
        ui_actions=result.ui_actions,
        debug=result.debug,
        action_required=result.action_required,
        proposed_changes=result.proposed_changes,
    )
