"""Health check routes."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.llm.client import LLMClient, LLMUnavailable

_READY_CACHE_LOCK = threading.Lock()
_READY_CACHE: dict[str, object] = {
    "expires_at": 0.0,
    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
    "payload": {
        "ok": False,
        "checks": {"db": "err", "llm": "err"},
        "details": {"db": None, "llm": None},
    },
}

router = APIRouter(tags=["health"])


def get_llm_client() -> LLMClient:
    return LLMClient()


LlmClientDep = Annotated[LLMClient, Depends(get_llm_client)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "SphereApp API", "status": "ok"}


def _copy_ready_payload(payload_obj: object) -> dict[str, object]:
    payload = payload_obj if isinstance(payload_obj, dict) else {}
    checks = payload.get("checks", {})
    details = payload.get("details", {})
    return {
        "ok": bool(payload.get("ok", False)),
        "checks": dict(checks if isinstance(checks, dict) else {}),
        "details": dict(details if isinstance(details, dict) else {}),
    }


def _readiness(llm_client: LLMClient) -> tuple[bool, bool | None, str | None]:
    db_status, _ = check_db()
    if db_status != "ok":
        return False, None, "DB_NOT_READY"

    if settings.ready_check_llm:
        try:
            llm_client.health_check()
        except LLMUnavailable:
            return True, False, "LLM_UNAVAILABLE"
        return True, True, None

    return True, None, None


def check_db() -> tuple[str, str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok", None
    except Exception as exc:
        return "err", str(exc)


def check_llm(llm_client: LLMClient) -> tuple[str, str | None]:
    try:
        llm_client.health_check()
        return "ok", None
    except Exception as exc:
        return "err", str(exc)


@router.get("/ready")
def ready(llm_client: LlmClientDep) -> dict[str, object]:
    with _READY_CACHE_LOCK:
        now = time.monotonic()
        expires_at = float(_READY_CACHE["expires_at"])
        if now < expires_at:
            payload = _copy_ready_payload(_READY_CACHE["payload"])
            status_code = int(_READY_CACHE["status_code"])
        else:
            checks: dict[str, str] = {"db": "err", "llm": "err"}
            details: dict[str, str | None] = {"db": None, "llm": None}

            db_status, db_err = check_db()
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
            status_code = status.HTTP_200_OK
            if checks["db"] != "ok":
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            ttl_seconds = max(0.0, float(settings.ready_db_cache_ttl_seconds))
            _READY_CACHE["payload"] = _copy_ready_payload(payload)
            _READY_CACHE["status_code"] = int(status_code)
            _READY_CACHE["expires_at"] = time.monotonic() + ttl_seconds

    if status_code != status.HTTP_200_OK:
        return JSONResponse(
            status_code=status_code,
            content=payload,
        )

    return payload


@router.get("/api/status")
def status_endpoint(llm_client: LlmClientDep) -> dict[str, object]:
    db_ready, llm_ready, reason = _readiness(llm_client)
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
