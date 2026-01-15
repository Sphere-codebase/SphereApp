"""Admin agencies endpoints."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.models import Agency, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    AgencyCreateRequest,
    AgencyResponse,
    AgencyUpdateRequest,
)

router = APIRouter(prefix="/api/admin/agencies", tags=["admin_agencies"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


def _slugify(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def _unique_slug(
    db: Session,
    tenant_id: uuid.UUID,
    slug: str,
    exclude_id: uuid.UUID | None = None,
) -> str | None:
    stmt = select(Agency).where(
        Agency.slug == slug,
        Agency.tenant_id == tenant_id,
    )
    if exclude_id is not None:
        stmt = stmt.where(Agency.id != exclude_id)
    return db.execute(stmt).scalar_one_or_none()


def _generate_unique_slug(db: Session, tenant_id: uuid.UUID, base: str) -> str:
    candidate = base
    suffix = 2
    while _unique_slug(db, tenant_id, candidate) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


@router.get("", response_model=list[AgencyResponse])
def list_agencies(db: DbSessionDep, current_user: AdminUserDep) -> list[AgencyResponse]:
    agencies = (
        db.execute(
            select(Agency)
            .where(Agency.tenant_id == current_user.tenant_id)
            .order_by(Agency.name.asc())
        )
        .scalars()
        .all()
    )
    return [AgencyResponse.model_validate(agency) for agency in agencies]


@router.post("", response_model=AgencyResponse, status_code=status.HTTP_201_CREATED)
def create_agency(
    payload: AgencyCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse | JSONResponse:
    name = payload.name.strip()
    if not name:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                code="INVALID_NAME",
                message="Agency name is required",
            ),
        )
    requested_slug = payload.slug.strip() if payload.slug is not None else ""
    if requested_slug:
        slug = _slugify(requested_slug)
        if not slug:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_payload(
                    code="INVALID_SLUG",
                    message="Slug must include letters or numbers",
                ),
            )
        if _unique_slug(db, current_user.tenant_id, slug) is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="AGENCY_EXISTS",
                    message="Agency already exists",
                    details={"slug": slug},
                ),
            )
    else:
        slug_base = _slugify(name)
        if not slug_base:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_payload(
                    code="INVALID_SLUG",
                    message="Slug must include letters or numbers",
                ),
            )
        slug = _generate_unique_slug(db, current_user.tenant_id, slug_base)
    agency = Agency(
        tenant_id=current_user.tenant_id,
        name=name,
        slug=slug,
        is_active=payload.is_active,
    )
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return AgencyResponse.model_validate(agency)


@router.get("/{agency_id}", response_model=AgencyResponse)
def get_agency(
    agency_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return AgencyResponse.model_validate(agency)


@router.patch("/{agency_id}", response_model=AgencyResponse)
def update_agency(
    agency_id: uuid.UUID,
    payload: AgencyUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> AgencyResponse | JSONResponse:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_payload(
                    code="INVALID_NAME",
                    message="Agency name is required",
                ),
            )
        agency.name = name
    if "slug" in updates:
        requested_slug = updates["slug"]
        if requested_slug is None or requested_slug.strip() == "":
            slug_base = _slugify(agency.name)
            if not slug_base:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content=error_payload(
                        code="INVALID_SLUG",
                        message="Slug must include letters or numbers",
                    ),
                )
            agency.slug = _generate_unique_slug(db, current_user.tenant_id, slug_base)
        else:
            slug = _slugify(requested_slug)
            if not slug:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content=error_payload(
                        code="INVALID_SLUG",
                        message="Slug must include letters or numbers",
                    ),
                )
            existing = _unique_slug(db, current_user.tenant_id, slug, exclude_id=agency.id)
            if existing is not None:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content=error_payload(
                        code="AGENCY_EXISTS",
                        message="Agency already exists",
                        details={"slug": slug},
                    ),
                )
            agency.slug = slug
    if "is_active" in updates:
        agency.is_active = updates["is_active"]
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return AgencyResponse.model_validate(agency)


@router.delete("/{agency_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_agency(
    agency_id: uuid.UUID,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    agency = db.execute(
        select(Agency).where(
            Agency.id == agency_id,
            Agency.tenant_id == current_user.tenant_id,
        )
    ).scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    agency.is_active = False
    db.add(agency)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
