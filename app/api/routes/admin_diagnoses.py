"""Admin diagnosis endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import Diagnosis, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    DiagnosisCreateRequest,
    DiagnosisResponse,
    DiagnosisUpdateRequest,
)

router = APIRouter(prefix="/api/admin/diagnoses", tags=["admin_diagnoses"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[DiagnosisResponse])
def list_diagnoses(
    db: DbSessionDep,
    current_user: AdminUserDep,
    query: Annotated[str | None, Query()] = None,
) -> list[DiagnosisResponse]:
    stmt = select(Diagnosis).where(Diagnosis.tenant_id == current_user.tenant_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(Diagnosis.code.ilike(like) | Diagnosis.title.ilike(like))
    diagnoses = db.execute(stmt.order_by(Diagnosis.code.asc())).scalars().all()
    return [DiagnosisResponse.model_validate(diagnosis) for diagnosis in diagnoses]


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_201_CREATED)
def create_diagnosis(
    payload: DiagnosisCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> DiagnosisResponse | JSONResponse:
    existing = (
        db.execute(
            select(Diagnosis).where(
                Diagnosis.code == payload.code,
                Diagnosis.tenant_id == current_user.tenant_id,
            )
        )
        .scalar_one_or_none()
    )
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="DIAGNOSIS_EXISTS",
                message="Diagnosis already exists",
                details={"code": payload.code},
            ),
        )
    diagnosis = Diagnosis(
        tenant_id=current_user.tenant_id,
        code=payload.code,
        title=payload.title,
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return DiagnosisResponse.model_validate(diagnosis)


@router.patch("/{diagnosis_id}", response_model=DiagnosisResponse)
def update_diagnosis(
    diagnosis_id: uuid.UUID,
    payload: DiagnosisUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> DiagnosisResponse | JSONResponse:
    diagnosis = (
        db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.tenant_id == current_user.tenant_id,
            )
        )
        .scalar_one_or_none()
    )
    if diagnosis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
    if payload.code and payload.code != diagnosis.code:
        existing = (
            db.execute(
                select(Diagnosis).where(
                    Diagnosis.code == payload.code,
                    Diagnosis.tenant_id == current_user.tenant_id,
                )
            )
            .scalar_one_or_none()
        )
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="DIAGNOSIS_EXISTS",
                    message="Diagnosis already exists",
                    details={"code": payload.code},
                ),
            )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(diagnosis, field, value)
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return DiagnosisResponse.model_validate(diagnosis)


@router.delete(
    "/{diagnosis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_diagnosis(
    diagnosis_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    diagnosis = (
        db.execute(
            select(Diagnosis).where(
                Diagnosis.id == diagnosis_id,
                Diagnosis.tenant_id == current_user.tenant_id,
            )
        )
        .scalar_one_or_none()
    )
    if diagnosis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
    db.delete(diagnosis)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
