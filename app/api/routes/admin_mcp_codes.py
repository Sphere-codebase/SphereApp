"""Admin MCP code endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_platform_staff_admin
from app.core.logging import error_payload
from app.db.models import McpCode, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    McpCodeCreateRequest,
    McpCodeResponse,
    McpCodeUpdateRequest,
)

router = APIRouter(prefix="/api/admin/mcp-codes", tags=["admin_mcp_codes"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("", response_model=list[McpCodeResponse])
def list_mcp_codes(db: DbSessionDep, current_user: AdminUserDep) -> list[McpCodeResponse]:
    codes = db.execute(select(McpCode).order_by(McpCode.code.asc())).scalars().all()
    return [McpCodeResponse.model_validate(code) for code in codes]


@router.post("", response_model=McpCodeResponse, status_code=status.HTTP_201_CREATED)
def create_mcp_code(
    payload: McpCodeCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> McpCodeResponse | JSONResponse:
    code_value = payload.code.strip()
    if not code_value:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(code="INVALID_CODE", message="Code is required"),
        )
    existing = db.execute(select(McpCode).where(McpCode.code == code_value)).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="MCP_CODE_EXISTS",
                message="MCP code already exists",
                details={"code": code_value},
            ),
        )
    code = McpCode(code=code_value, description=payload.description)
    db.add(code)
    db.commit()
    db.refresh(code)
    audit.log_event(
        action="CREATE",
        entity="mcp_code",
        entity_id=code.code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": ["code", "description"]},
        scope="platform",
    )
    return McpCodeResponse.model_validate(code)


@router.get("/{code}", response_model=McpCodeResponse)
def get_mcp_code(
    code: str,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> McpCodeResponse:
    mcp_code = db.execute(select(McpCode).where(McpCode.code == code)).scalar_one_or_none()
    if mcp_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    return McpCodeResponse.model_validate(mcp_code)


@router.patch("/{code}", response_model=McpCodeResponse)
def update_mcp_code(
    code: str,
    payload: McpCodeUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> McpCodeResponse:
    mcp_code = db.execute(select(McpCode).where(McpCode.code == code)).scalar_one_or_none()
    if mcp_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    updates = payload.model_dump(exclude_unset=True)
    if "description" in updates:
        mcp_code.description = updates["description"]
    db.add(mcp_code)
    db.commit()
    db.refresh(mcp_code)
    audit.log_event(
        action="UPDATE",
        entity="mcp_code",
        entity_id=mcp_code.code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": list(updates.keys())},
        scope="platform",
    )
    return McpCodeResponse.model_validate(mcp_code)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_mcp_code(
    code: str,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> Response:
    mcp_code = db.execute(select(McpCode).where(McpCode.code == code)).scalar_one_or_none()
    if mcp_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    db.delete(mcp_code)
    db.commit()
    audit.log_event(
        action="DELETE",
        entity="mcp_code",
        entity_id=code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        scope="platform",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
