"""Admin policy link endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.logging import error_payload
from app.db.id_utils import next_id
from app.db.models import InsuranceCompany, McpCode, PolicyLink, User
from app.db.session import get_db
from app.schemas.admin_catalogs import (
    PolicyLinkCreateRequest,
    PolicyLinkResponse,
    PolicyLinkUpdateRequest,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/admin/policy-links", tags=["admin_policy_links"])
DbSessionDep = Annotated[Session, Depends(get_db)]
AdminUserDep = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[PolicyLinkResponse])
def list_policy_links(
    db: DbSessionDep,
    current_user: AdminUserDep,
    insurance_company_id: Annotated[int | None, Query()] = None,
    mcp_code: Annotated[str | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
) -> list[PolicyLinkResponse]:
    stmt = select(PolicyLink)
    if insurance_company_id:
        stmt = stmt.where(PolicyLink.insurance_company_id == insurance_company_id)
    if mcp_code:
        stmt = stmt.where(PolicyLink.mcp_code == mcp_code)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(PolicyLink.policy_url.ilike(like))
    links = db.execute(stmt.order_by(PolicyLink.created_at.desc())).scalars().all()
    return [PolicyLinkResponse.model_validate(link) for link in links]


@router.post("", response_model=PolicyLinkResponse, status_code=status.HTTP_201_CREATED)
def create_policy_link(
    payload: PolicyLinkCreateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> PolicyLinkResponse | JSONResponse:
    company = db.execute(
        select(InsuranceCompany).where(InsuranceCompany.id == payload.insurance_company_id)
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    code = db.execute(select(McpCode).where(McpCode.code == payload.mcp_code)).scalar_one_or_none()
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")
    existing = db.execute(
        select(PolicyLink).where(
            PolicyLink.insurance_company_id == payload.insurance_company_id,
            PolicyLink.mcp_code == payload.mcp_code,
            PolicyLink.policy_url == str(payload.policy_url),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="POLICY_LINK_EXISTS",
                message="Policy link already exists",
            ),
        )
    link = PolicyLink(
        id=next_id(db, PolicyLink),
        insurance_company_id=payload.insurance_company_id,
        mcp_code=payload.mcp_code,
        policy_url=str(payload.policy_url),
        created_at=utcnow(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return PolicyLinkResponse.model_validate(link)


@router.patch("/{policy_link_id}", response_model=PolicyLinkResponse)
def update_policy_link(
    policy_link_id: int,
    payload: PolicyLinkUpdateRequest,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> PolicyLinkResponse | JSONResponse:
    link = db.execute(select(PolicyLink).where(PolicyLink.id == policy_link_id)).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy link not found")
    data = payload.model_dump(exclude_unset=True)
    insurance_company_id = data.get("insurance_company_id", link.insurance_company_id)
    mcp_code = data.get("mcp_code", link.mcp_code)
    policy_url = data.get("policy_url", link.policy_url)

    if "insurance_company_id" in data:
        company = db.execute(
            select(InsuranceCompany).where(InsuranceCompany.id == insurance_company_id)
        ).scalar_one_or_none()
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if "mcp_code" in data:
        code = db.execute(select(McpCode).where(McpCode.code == mcp_code)).scalar_one_or_none()
        if code is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP code not found")

    existing = db.execute(
        select(PolicyLink).where(
            PolicyLink.insurance_company_id == insurance_company_id,
            PolicyLink.mcp_code == mcp_code,
            PolicyLink.policy_url == str(policy_url),
            PolicyLink.id != link.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_payload(
                code="POLICY_LINK_EXISTS",
                message="Policy link already exists",
            ),
        )

    for field, value in data.items():
        if field == "policy_url" and value is not None:
            value = str(value)
        setattr(link, field, value)
    db.add(link)
    db.commit()
    db.refresh(link)
    return PolicyLinkResponse.model_validate(link)


@router.delete(
    "/{policy_link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_policy_link(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: AdminUserDep,
) -> Response:
    link = db.execute(select(PolicyLink).where(PolicyLink.id == policy_link_id)).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy link not found")
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
