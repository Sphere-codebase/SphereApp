"""Health check routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.llm.client import LLMClient, LLMUnavailable

router = APIRouter(tags=["health"])
DbSessionDep = Annotated[Session, Depends(get_db)]


def get_llm_client() -> LLMClient:
    return LLMClient()


LlmClientDep = Annotated[LLMClient, Depends(get_llm_client)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _readiness(db: Session, llm_client: LLMClient) -> tuple[bool, bool | None, str | None]:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return False, None, "DB_NOT_READY"

    if settings.ready_check_llm:
        try:
            llm_client.health_check()
        except LLMUnavailable:
            return True, False, "LLM_UNAVAILABLE"
        return True, True, None

    return True, None, None


@router.get("/ready")
def ready(db: DbSessionDep, llm_client: LlmClientDep) -> dict[str, str]:
    db_ready, llm_ready, reason = _readiness(db, llm_client)
    if not db_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not ready"
        )
    if settings.ready_check_llm and llm_ready is False:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM unavailable"
        )
    return {"status": "ready"}


@router.get("/api/status")
def status_endpoint(db: DbSessionDep, llm_client: LlmClientDep) -> dict[str, object]:
    db_ready, llm_ready, reason = _readiness(db, llm_client)
    overall_ready = db_ready and (llm_ready in (True, None))
    checked_at = datetime.now().isoformat(timespec="seconds")
    return {
        "db_ready": db_ready,
        "llm_ready": llm_ready,
        "overall_ready": overall_ready,
        "reason": reason,
        "checked_at": checked_at,
        "env": settings.env,
        "llm_model": settings.llm_model,
        "lmstudio_base_url": settings.lmstudio_base_url,
        "llm_max_steps": settings.llm_max_steps,
    }
