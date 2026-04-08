"""Admin diagnosis code endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, require_platform_staff_admin
from app.core.config import settings
from app.core.logging import error_payload
from app.core.response_cache import admin_ref_response_cache
from app.db.models import DiagnosisCode, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    DiagnosisCodeCreateRequest,
    DiagnosisCodeResponse,
    DiagnosisCodeUpdateRequest,
)

router = APIRouter(prefix="/api/admin/diagnosis-codes", tags=["admin_diagnosis_codes"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("", response_model=list[DiagnosisCodeResponse])
def list_diagnosis_codes(
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> list[DiagnosisCodeResponse]:
    cache_key = (
        "admin_ref",
        "diagnosis_codes",
        current_user.id,
        current_user.clinic_id,
        current_user.role,
        current_user.role == "platform_staff_admin",
    )

    def _load_payload() -> list[dict[str, object]]:
        codes = db.execute(select(DiagnosisCode).order_by(DiagnosisCode.code.asc())).scalars().all()
        return [
            DiagnosisCodeResponse.model_validate(code).model_dump(mode="json") for code in codes
        ]

    payload = admin_ref_response_cache.get_or_set(
        cache_key,
        settings.admin_ref_cache_ttl_seconds,
        _load_payload,
    )
    return [DiagnosisCodeResponse.model_validate(item) for item in payload]


@router.post("", response_model=DiagnosisCodeResponse, status_code=status.HTTP_201_CREATED)
def create_diagnosis_code(
    payload: DiagnosisCodeCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
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
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "diagnosis_codes"))
    audit.log_event(
        action="CREATE",
        entity="diagnosis_code",
        entity_id=code.code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": ["code", "description"]},
        scope="platform",
    )
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
    audit: AuditLoggerDep,
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
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "diagnosis_codes"))
    audit.log_event(
        action="UPDATE",
        entity="diagnosis_code",
        entity_id=diagnosis_code.code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": list(updates.keys())},
        scope="platform",
    )
    return DiagnosisCodeResponse.model_validate(diagnosis_code)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_diagnosis_code(
    code: str,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
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
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "diagnosis_codes"))
    audit.log_event(
        action="DELETE",
        entity="diagnosis_code",
        entity_id=code,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        scope="platform",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
