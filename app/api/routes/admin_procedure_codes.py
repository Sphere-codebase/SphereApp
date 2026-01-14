"""Admin procedure code endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import ProcedureCode, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    ProcedureCodeCreateRequest,
    ProcedureCodeResponse,
    ProcedureCodeUpdateRequest,
)

router = APIRouter(prefix="/api/admin/procedure-codes", tags=["admin_procedure_codes"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[ProcedureCodeResponse])
def list_procedure_codes(
    db: DbSessionDep,
    _: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[ProcedureCodeResponse]:
    stmt = select(ProcedureCode)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            ProcedureCode.code.ilike(like) | ProcedureCode.title.ilike(like)
        )
    codes = db.execute(stmt.order_by(ProcedureCode.code.asc())).scalars().all()
    return [ProcedureCodeResponse.model_validate(code) for code in codes]


@router.post("", response_model=ProcedureCodeResponse, status_code=status.HTTP_201_CREATED)
def create_procedure_code(
    payload: ProcedureCodeCreateRequest,
    db: DbSessionDep,
    _: AdminUserDep,
) -> ProcedureCodeResponse | JSONResponse:
    existing = (
        db.execute(select(ProcedureCode).where(ProcedureCode.code == payload.code))
        .scalar_one_or_none()
    )
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="PROCEDURE_CODE_EXISTS",
                message="Procedure code already exists",
                details={"code": payload.code},
            ),
        )
    code = ProcedureCode(code=payload.code, title=payload.title, category=payload.category)
    db.add(code)
    db.commit()
    db.refresh(code)
    return ProcedureCodeResponse.model_validate(code)


@router.patch("/{procedure_code_id}", response_model=ProcedureCodeResponse)
def update_procedure_code(
    procedure_code_id: uuid.UUID,
    payload: ProcedureCodeUpdateRequest,
    db: DbSessionDep,
    _: AdminUserDep,
) -> ProcedureCodeResponse | JSONResponse:
    code = (
        db.execute(select(ProcedureCode).where(ProcedureCode.id == procedure_code_id))
        .scalar_one_or_none()
    )
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Procedure code not found",
        )
    if payload.code and payload.code != code.code:
        existing = (
            db.execute(select(ProcedureCode).where(ProcedureCode.code == payload.code))
            .scalar_one_or_none()
        )
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="PROCEDURE_CODE_EXISTS",
                    message="Procedure code already exists",
                    details={"code": payload.code},
                ),
            )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(code, field, value)
    db.add(code)
    db.commit()
    db.refresh(code)
    return ProcedureCodeResponse.model_validate(code)


@router.delete(
    "/{procedure_code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_procedure_code(
    procedure_code_id: uuid.UUID,
    db: DbSessionDep,
    _: AdminUserDep,
) -> Response:
    code = (
        db.execute(select(ProcedureCode).where(ProcedureCode.id == procedure_code_id))
        .scalar_one_or_none()
    )
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Procedure code not found",
        )
    db.delete(code)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
