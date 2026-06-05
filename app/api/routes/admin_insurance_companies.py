"""Admin insurance company endpoints."""

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
from app.db.id_utils import next_id
from app.db.models import InsuranceCompany, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    InsuranceCompanyCreateRequest,
    InsuranceCompanyResponse,
    InsuranceCompanyUpdateRequest,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/admin/insurance-companies", tags=["admin_insurance_companies"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_platform_staff_admin)]


@router.get("", response_model=list[InsuranceCompanyResponse])
def list_insurance_companies(
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> list[InsuranceCompanyResponse]:
    cache_key = (
        "admin_ref",
        "insurance_companies",
        current_user.id,
        current_user.clinic_id,
        current_user.role,
        current_user.role == "platform_staff_admin",
    )

    def _load_payload() -> list[dict[str, object]]:
        companies = (
            db.execute(select(InsuranceCompany).order_by(InsuranceCompany.name.asc()))
            .scalars()
            .all()
        )
        return [
            InsuranceCompanyResponse.model_validate(company).model_dump(mode="json")
            for company in companies
        ]

    payload = admin_ref_response_cache.get_or_set(
        cache_key,
        settings.admin_ref_cache_ttl_seconds,
        _load_payload,
    )
    return [InsuranceCompanyResponse.model_validate(item) for item in payload]


@router.post("", response_model=InsuranceCompanyResponse, status_code=status.HTTP_201_CREATED)
def create_insurance_company(
    payload: InsuranceCompanyCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> InsuranceCompanyResponse | JSONResponse:
    name = payload.name.strip()
    if not name:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                code="INVALID_NAME",
                message="Insurance company name is required",
            ),
        )
    existing = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="INSURANCE_COMPANY_EXISTS",
                message="Insurance company already exists",
                details={"name": name},
            ),
        )
    stedi_id = (
        payload.stedi_trading_partner_service_id.strip()
        if payload.stedi_trading_partner_service_id
        else None
    )
    company = InsuranceCompany(
        id=next_id(db, InsuranceCompany),
        name=name,
        stedi_trading_partner_service_id=stedi_id,
        created_at=utcnow(),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "insurance_companies"))
    audit.log_event(
        action="CREATE",
        entity="insurance_company",
        entity_id=company.id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": ["name", "stedi_trading_partner_service_id"]},
        scope="platform",
    )
    return InsuranceCompanyResponse.model_validate(company)


@router.get("/{company_id}", response_model=InsuranceCompanyResponse)
def get_insurance_company(
    company_id: int,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> InsuranceCompanyResponse:
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == company_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insurance company not found"
        )
    return InsuranceCompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=InsuranceCompanyResponse)
def update_insurance_company(
    company_id: int,
    payload: InsuranceCompanyUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> InsuranceCompanyResponse | JSONResponse:
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == company_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insurance company not found"
        )
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_payload(
                    code="INVALID_NAME",
                    message="Insurance company name is required",
                ),
            )
        existing = db.execute(
            select(InsuranceCompany).where(
                InsuranceCompany.name == name, InsuranceCompany.id != company.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=error_payload(
                    code="INSURANCE_COMPANY_EXISTS",
                    message="Insurance company already exists",
                    details={"name": name},
                ),
            )
        company.name = name
    if "stedi_trading_partner_service_id" in updates:
        stedi_id = updates["stedi_trading_partner_service_id"]
        company.stedi_trading_partner_service_id = stedi_id.strip() if stedi_id else None
    db.add(company)
    db.commit()
    db.refresh(company)
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "insurance_companies"))
    audit.log_event(
        action="UPDATE",
        entity="insurance_company",
        entity_id=company.id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        diff={"fields": list(updates.keys())},
        scope="platform",
    )
    return InsuranceCompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_insurance_company(
    company_id: int,
    db: DbSessionDep,
    current_user: AdminUserDep,
    audit: AuditLoggerDep,
) -> Response:
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == company_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insurance company not found"
        )
    db.delete(company)
    db.commit()
    admin_ref_response_cache.invalidate_prefix(("admin_ref", "insurance_companies"))
    audit.log_event(
        action="DELETE",
        entity="insurance_company",
        entity_id=company_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        scope="platform",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
