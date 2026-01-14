"""API dependency helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.db.models import User

CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUserDep) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user
