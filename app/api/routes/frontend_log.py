"""Frontend log ingestion (dev-only)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/frontend-log", tags=["frontend_log"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

RATE_BUCKET: dict[str, list[float]] = {}
FORBIDDEN_KEYS = {"authorization", "access_token", "password", "cookie", "cookies"}


def _ensure_enabled() -> None:
    if settings.env == "dev" or settings.frontend_file_logs:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Frontend logging disabled")


def _rate_limit(user_id: str) -> None:
    now = time.monotonic()
    window = 1.0
    limit = settings.frontend_log_rate_per_sec
    history = RATE_BUCKET.get(user_id, [])
    history = [ts for ts in history if now - ts < window]
    if len(history) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit")
    history.append(now)
    RATE_BUCKET[user_id] = history


def _contains_forbidden(data: Any) -> bool:
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return True
            if _contains_forbidden(value):
                return True
        return False
    if isinstance(data, list):
        return any(_contains_forbidden(item) for item in data)
    if isinstance(data, str):
        lowered = data.lower()
        if "bearer " in lowered or "authorization" in lowered:
            return True
        return False
    return False


def _log_path() -> Path:
    return Path(settings.frontend_log_path)


@router.post(
    "/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
def reset_frontend_log(_: DbSessionDep, current_user: CurrentUserDep) -> Response:
    _ensure_enabled()
    _rate_limit(str(current_user.id))
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def append_frontend_log(
    request: Request,
    _: DbSessionDep,
    current_user: CurrentUserDep,
) -> Response:
    _ensure_enabled()
    _rate_limit(str(current_user.id))
    data_bytes = await request.body()
    if len(data_bytes) > settings.frontend_log_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Too large",
        )

    try:
        payload = json.loads(data_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    if _contains_forbidden(payload):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Forbidden keys")

    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, default=str)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
