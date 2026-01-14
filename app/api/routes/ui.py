"""HTML UI routes."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

router = APIRouter(tags=["ui"])
ROOT_DIR = Path(__file__).resolve().parents[3]
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))
DbSessionDep = Annotated[Session, Depends(get_db)]


def get_current_user_from_cookie(request: Request, db: DbSessionDep) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            return None
        user_id = uuid.UUID(subject)
    except (HTTPException, ValueError):
        return None

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/app/chat", response_class=HTMLResponse)
def chat_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_from_cookie)],
) -> Response:
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"user": current_user},
    )


@router.get("/app/admin/users", response_class=HTMLResponse)
def admin_users_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_from_cookie)],
) -> Response:
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {"user": current_user},
    )
