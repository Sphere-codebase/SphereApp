"""Admin diagnosis code endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import DiagnosisCode, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    DiagnosisCodeCreateRequest,
    DiagnosisCodeResponse,
    DiagnosisCodeUpdateRequest,
)

router = APIRouter(prefix="/api/admin/diagnosis-codes", tags=["admin_diagnosis_codes"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[DiagnosisCodeResponse])
def list_diagnosis_codes(
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> list[DiagnosisCodeResponse]:
    codes = db.execute(select(DiagnosisCode).order_by(DiagnosisCode.code.asc())).scalars().all()
    return [DiagnosisCodeResponse.model_validate(code) for code in codes]


@router.post("", response_model=DiagnosisCodeResponse, status_code=status.HTTP_201_CREATED)
def create_diagnosis_code(
    payload: DiagnosisCodeCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> DiagnosisCodeResponse | JSONResponse:
    code_value = payload.code.strip()
    if not code_value:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(code="INVALID_CODE", message="Code is required"),
        )
    existing = db.execute(
        select(DiagnosisCode).where(DiagnosisCode.code == code_value)
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="DIAGNOSIS_CODE_EXISTS",
                message="Diagnosis code already exists",
                details={"code": code_value},
            ),
        )
    code = DiagnosisCode(code=code_value, description=payload.description)
    db.add(code)
    db.commit()
    db.refresh(code)
    return DiagnosisCodeResponse.model_validate(code)


@router.get("/{code}", response_model=DiagnosisCodeResponse)
def get_diagnosis_code(
    code: str,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> DiagnosisCodeResponse:
    diagnosis_code = db.execute(
        select(DiagnosisCode).where(DiagnosisCode.code == code)
    ).scalar_one_or_none()
    if diagnosis_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not found"
        )
    return DiagnosisCodeResponse.model_validate(diagnosis_code)


@router.patch("/{code}", response_model=DiagnosisCodeResponse)
def update_diagnosis_code(
    code: str,
    payload: DiagnosisCodeUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> DiagnosisCodeResponse:
    diagnosis_code = db.execute(
        select(DiagnosisCode).where(DiagnosisCode.code == code)
    ).scalar_one_or_none()
    if diagnosis_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not found"
        )
    updates = payload.model_dump(exclude_unset=True)
    if "description" in updates:
        diagnosis_code.description = updates["description"]
    db.add(diagnosis_code)
    db.commit()
    db.refresh(diagnosis_code)
    return DiagnosisCodeResponse.model_validate(diagnosis_code)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_diagnosis_code(
    code: str,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    diagnosis_code = db.execute(
        select(DiagnosisCode).where(DiagnosisCode.code == code)
    ).scalar_one_or_none()
    if diagnosis_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis code not found"
        )
    db.delete(diagnosis_code)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
