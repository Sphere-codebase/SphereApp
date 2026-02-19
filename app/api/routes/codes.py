"""Code search endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import DiagnosisCode, McpCode, User
from app.db.session import get_db
from app.schemas.codes import DiagnosisCodeItem, McpCodeItem

router = APIRouter(prefix="/api/codes", tags=["codes"])
DbSessionDep = Annotated[Session, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/mcp", response_model=list[McpCodeItem])
def search_mcp_codes(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[McpCodeItem]:
    if not query or not query.strip():
        return []
    like = f"%{query.strip()}%"
    codes = (
        db.execute(
            select(McpCode)
            .where(or_(McpCode.code.ilike(like), McpCode.description.ilike(like)))
            .order_by(McpCode.code.asc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    return [McpCodeItem.model_validate(code) for code in codes]


@router.get("/diagnosis", response_model=list[DiagnosisCodeItem])
def search_diagnosis_codes(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[DiagnosisCodeItem]:
    if not query or not query.strip():
        return []
    like = f"%{query.strip()}%"
    codes = (
        db.execute(
            select(DiagnosisCode)
            .where(or_(DiagnosisCode.code.ilike(like), DiagnosisCode.description.ilike(like)))
            .order_by(DiagnosisCode.code.asc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    return [DiagnosisCodeItem.model_validate(code) for code in codes]
