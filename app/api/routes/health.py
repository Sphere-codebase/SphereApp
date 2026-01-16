"""Health check routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.llm.client import LLMClient, LLMUnavailable

_LAST: dict[str, object] = {
    "checks": {"db": "err", "llm": "err"},
    "details": {"db": None, "llm": None},
    "ok": False,
    "ts": 0.0,
}

SKIP_PING_TTL_SECONDS = 10.0

router = APIRouter(tags=["health"])
DbSessionDep = Annotated[Session, Depends(get_db)]


def get_llm_client() -> LLMClient:
    return LLMClient()


LlmClientDep = Annotated[LLMClient, Depends(get_llm_client)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "SphereApp API", "status": "ok"}


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


def check_db(db: DbSessionDep) -> tuple[str, str | None]:
    try:
        db.execute(text("SELECT 1"))
        return "ok", None
    except Exception as exc:
        return "err", str(exc)


def check_llm(llm_client: LlmClientDep) -> tuple[str, str | None]:
    try:
        llm_client.health_check()
        return "ok", None
    except Exception as exc:
        return "err", str(exc)


@router.get("/ready")
def ready(db: DbSessionDep, llm_client: LlmClientDep) -> dict[str, object]:
    # print(float(_LAST["ts"]))
    last_checks = _LAST["checks"]
    assert isinstance(last_checks, dict)

    if (
        last_checks.get("db") == "ok"
        and last_checks.get("llm") == "ok"
        and float(_LAST["ts"]) < SKIP_PING_TTL_SECONDS
    ):
        _LAST["ts"] += 0.1
        payload = {
            "ok": bool(_LAST["ok"]),
            "checks": dict(_LAST["checks"]),
            "details": dict(_LAST["details"]),
        }
        return payload

    checks: dict[str, str] = {"db": "err", "llm": "err"}
    details: dict[str, str | None] = {"db": None, "llm": None}

    db_status, db_err = check_db(db)
    checks["db"] = db_status
    details["db"] = db_err

    if settings.ready_check_llm:
        llm_status, llm_err = check_llm(llm_client)
        checks["llm"] = llm_status
        details["llm"] = llm_err
    else:
        checks["llm"] = "warn"
        details["llm"] = "LLM check disabled"

    overall_ok = checks["db"] == "ok"
    payload = {"ok": overall_ok, "checks": checks, "details": details}

    _LAST["checks"] = checks
    _LAST["details"] = details
    _LAST["ok"] = overall_ok
    _LAST["ts"] = 9

    # print(_LAST)
    if checks["db"] != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    return payload


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
