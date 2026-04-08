"""Insurance rules viewer and overrides endpoints."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuditLoggerDep, CurrentUserDep, require_roles
from app.db.id_utils import next_id
from app.db.models import (
    ClinicPolicyOverride,
    DoctorPolicyOverride,
    PolicyLink,
    PolicyRule,
)
from app.db.session import get_db
from app.schemas.insurance_rules import (
    ClinicOverrideResponse,
    DoctorOverrideResponse,
    OverrideUpsertRequest,
    PolicyLinkItem,
    PolicyLinkListResponse,
    PolicyRulesResponse,
)
from app.utils.time import utcnow

router = APIRouter(prefix="/api/insurance-rules", tags=["insurance_rules"])
DbSessionDep = Annotated[Session, Depends(get_db)]


def _require_policy_link(db: Session, policy_link_id: int) -> PolicyLink:
    link = db.execute(
        select(PolicyLink).where(PolicyLink.id == policy_link_id)
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy link not found")
    return link


@router.get("/policy-links", response_model=PolicyLinkListResponse)
def list_policy_links(
    db: DbSessionDep,
    current_user: CurrentUserDep,
    insurance_company_id: Annotated[int | None, Query()] = None,
    mcp_code: Annotated[str | None, Query()] = None,
) -> PolicyLinkListResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    stmt = select(PolicyLink)
    if insurance_company_id is not None:
        stmt = stmt.where(PolicyLink.insurance_company_id == insurance_company_id)
    if mcp_code:
        stmt = stmt.where(PolicyLink.mcp_code == mcp_code)
    links = db.execute(stmt.order_by(PolicyLink.created_at.desc())).scalars().all()
    return PolicyLinkListResponse(
        items=[
            PolicyLinkItem(
                id=link.id,
                insurance_company_id=link.insurance_company_id,
                mcp_code=link.mcp_code,
                policy_url=link.policy_url,
            )
            for link in links
        ]
    )


@router.get("/{policy_link_id}/rules", response_model=PolicyRulesResponse)
def get_latest_policy_rules(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> PolicyRulesResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)
    rule = (
        db.execute(
            select(PolicyRule)
            .where(PolicyRule.policy_link_id == policy_link_id)
            .order_by(PolicyRule.extracted_at.desc())
        )
        .scalars()
        .first()
    )
    if rule is None:
        return PolicyRulesResponse(
            policy_link_id=policy_link_id, extracted_at=None, rules_json=None
        )

    parsed_rules = None
    if rule.rules_json:
        try:
            parsed_rules = json.loads(rule.rules_json)
        except json.JSONDecodeError:
            parsed_rules = {"raw": rule.rules_json}

    return PolicyRulesResponse(
        policy_link_id=rule.policy_link_id,
        extracted_at=rule.extracted_at,
        rules_json=parsed_rules,
    )


@router.get("/{policy_link_id}/clinic-override", response_model=ClinicOverrideResponse)
def get_clinic_override(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> ClinicOverrideResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)
    override = db.execute(
        select(ClinicPolicyOverride).where(
            ClinicPolicyOverride.policy_link_id == policy_link_id,
            ClinicPolicyOverride.clinic_id == current_user.clinic_id,
        )
    ).scalar_one_or_none()
    if override is None:
        return ClinicOverrideResponse(
            policy_link_id=policy_link_id,
            clinic_id=current_user.clinic_id,
            override_json=None,
            updated_at=None,
        )
    return ClinicOverrideResponse(
        policy_link_id=override.policy_link_id,
        clinic_id=override.clinic_id,
        override_json=override.override_json,
        updated_at=override.updated_at,
    )


@router.put("/{policy_link_id}/clinic-override", response_model=ClinicOverrideResponse)
def upsert_clinic_override(
    policy_link_id: int,
    payload: OverrideUpsertRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> ClinicOverrideResponse:
    require_roles("chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)

    override = db.execute(
        select(ClinicPolicyOverride).where(
            ClinicPolicyOverride.policy_link_id == policy_link_id,
            ClinicPolicyOverride.clinic_id == current_user.clinic_id,
        )
    ).scalar_one_or_none()

    previous = override.override_json if override else None
    if override is None:
        override = ClinicPolicyOverride(
            id=next_id(db, ClinicPolicyOverride),
            clinic_id=current_user.clinic_id,
            policy_link_id=policy_link_id,
            override_json=payload.override_json,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        override.override_json = payload.override_json
        override.updated_at = utcnow()

    db.add(override)
    db.commit()
    db.refresh(override)

    audit.log_event(
        action="insurance_rules.clinic_override_updated",
        entity="policy_link",
        entity_id=policy_link_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={"override_type": "clinic", "previous": previous, "new": payload.override_json},
        scope="clinic",
        actor_role=current_user.role,
    )

    return ClinicOverrideResponse(
        policy_link_id=override.policy_link_id,
        clinic_id=override.clinic_id,
        override_json=override.override_json,
        updated_at=override.updated_at,
    )


@router.delete("/{policy_link_id}/clinic-override", status_code=status.HTTP_204_NO_CONTENT)
def delete_clinic_override(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    require_roles("chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)
    override = db.execute(
        select(ClinicPolicyOverride).where(
            ClinicPolicyOverride.policy_link_id == policy_link_id,
            ClinicPolicyOverride.clinic_id == current_user.clinic_id,
        )
    ).scalar_one_or_none()
    if override is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    previous = override.override_json
    db.delete(override)
    db.commit()
    audit.log_event(
        action="insurance_rules.clinic_override_cleared",
        entity="policy_link",
        entity_id=policy_link_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={"override_type": "clinic", "previous": previous},
        scope="clinic",
        actor_role=current_user.role,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{policy_link_id}/doctor-override", response_model=DoctorOverrideResponse)
def get_doctor_override(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
) -> DoctorOverrideResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)
    override = db.execute(
        select(DoctorPolicyOverride).where(
            DoctorPolicyOverride.policy_link_id == policy_link_id,
            DoctorPolicyOverride.doctor_id == current_user.id,
        )
    ).scalar_one_or_none()
    if override is None:
        return DoctorOverrideResponse(
            policy_link_id=policy_link_id,
            doctor_id=current_user.id,
            override_json=None,
            updated_at=None,
        )
    if override.clinic_id != current_user.clinic_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return DoctorOverrideResponse(
        policy_link_id=override.policy_link_id,
        doctor_id=override.doctor_id,
        override_json=override.override_json,
        updated_at=override.updated_at,
    )


@router.put("/{policy_link_id}/doctor-override", response_model=DoctorOverrideResponse)
def upsert_doctor_override(
    policy_link_id: int,
    payload: OverrideUpsertRequest,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> DoctorOverrideResponse:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)

    override = db.execute(
        select(DoctorPolicyOverride).where(
            DoctorPolicyOverride.policy_link_id == policy_link_id,
            DoctorPolicyOverride.doctor_id == current_user.id,
        )
    ).scalar_one_or_none()

    previous = override.override_json if override else None
    if override is None:
        override = DoctorPolicyOverride(
            id=next_id(db, DoctorPolicyOverride),
            doctor_id=current_user.id,
            clinic_id=current_user.clinic_id,
            policy_link_id=policy_link_id,
            override_json=payload.override_json,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        if override.clinic_id != current_user.clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        override.override_json = payload.override_json
        override.updated_at = utcnow()

    db.add(override)
    db.commit()
    db.refresh(override)

    audit.log_event(
        action="insurance_rules.doctor_override_updated",
        entity="policy_link",
        entity_id=policy_link_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={
            "override_type": "doctor",
            "doctor_id": current_user.id,
            "previous": previous,
            "new": payload.override_json,
        },
        scope="clinic",
        actor_role=current_user.role,
    )

    return DoctorOverrideResponse(
        policy_link_id=override.policy_link_id,
        doctor_id=override.doctor_id,
        override_json=override.override_json,
        updated_at=override.updated_at,
    )


@router.delete("/{policy_link_id}/doctor-override", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor_override(
    policy_link_id: int,
    db: DbSessionDep,
    current_user: CurrentUserDep,
    audit: AuditLoggerDep,
) -> Response:
    require_roles("doctor", "chief_doctor", "clinic_admin")(current_user)
    _require_policy_link(db, policy_link_id)

    override = db.execute(
        select(DoctorPolicyOverride).where(
            DoctorPolicyOverride.policy_link_id == policy_link_id,
            DoctorPolicyOverride.doctor_id == current_user.id,
        )
    ).scalar_one_or_none()
    if override is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if override.clinic_id != current_user.clinic_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    previous = override.override_json
    db.delete(override)
    db.commit()
    audit.log_event(
        action="insurance_rules.doctor_override_cleared",
        entity="policy_link",
        entity_id=policy_link_id,
        actor=current_user,
        clinic_id=current_user.clinic_id,
        target_clinic_id=current_user.clinic_id,
        diff={"override_type": "doctor", "doctor_id": current_user.id, "previous": previous},
        scope="clinic",
        actor_role=current_user.role,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
