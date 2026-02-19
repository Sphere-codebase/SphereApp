"""Claim requirements engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Claim,
    ClaimDiagnosisCode,
    ClaimMcpCode,
    ClaimProcedureFact,
    PolicyLink,
    PolicyRule,
)


@dataclass(frozen=True)
class PolicyRuleSnapshot:
    policy_link_id: int
    extracted_at: Any | None
    rules_json: Any | None


def _parse_rules_json(raw: str | None) -> Any | None:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _rules_to_text(value: Any | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    try:
        return json.dumps(value).lower()
    except TypeError:
        return str(value).lower()


def _detect_policy_flags(rule_payloads: list[Any]) -> dict[str, bool]:
    text = " ".join(_rules_to_text(payload) for payload in rule_payloads if payload is not None)
    flags = {
        "requires_diagnosis": False,
        "requires_pos": False,
        "requires_units": False,
        "requires_prior_auth": False,
        "requires_modifier": False,
    }
    if not text:
        return flags

    if "diagnosis" in text and any(token in text for token in ("required", "must", "need")):
        flags["requires_diagnosis"] = True
    if "place of service" in text or "pos" in text:
        flags["requires_pos"] = True
    if "unit" in text and any(token in text for token in ("required", "must", "need")):
        flags["requires_units"] = True
    if "prior authorization" in text or "prior auth" in text:
        flags["requires_prior_auth"] = True
    if "modifier" in text and any(token in text for token in ("required", "must", "need")):
        flags["requires_modifier"] = True
    return flags


def _latest_policy_rules(db: Session, policy_link_ids: list[int]) -> dict[int, PolicyRule]:
    if not policy_link_ids:
        return {}
    latest_subq = (
        select(
            PolicyRule.policy_link_id,
            func.max(PolicyRule.extracted_at).label("latest_extracted"),
        )
        .where(PolicyRule.policy_link_id.in_(policy_link_ids))
        .group_by(PolicyRule.policy_link_id)
        .subquery()
    )
    rows = (
        db.execute(
            select(PolicyRule)
            .join(
                latest_subq,
                (PolicyRule.policy_link_id == latest_subq.c.policy_link_id)
                & (PolicyRule.extracted_at == latest_subq.c.latest_extracted),
            )
        )
        .scalars()
        .all()
    )
    return {row.policy_link_id: row for row in rows}


def get_policy_links_for_claim(
    db: Session,
    claim: Claim,
    mcp_codes: list[str],
) -> list[PolicyLink]:
    if not claim.insurance_company_id or not mcp_codes:
        return []
    return (
        db.execute(
            select(PolicyLink).where(
                PolicyLink.insurance_company_id == claim.insurance_company_id,
                PolicyLink.mcp_code.in_(mcp_codes),
            )
        )
        .scalars()
        .all()
    )


def build_policy_rule_snapshots(
    db: Session,
    policy_links: list[PolicyLink],
) -> list[PolicyRuleSnapshot]:
    if not policy_links:
        return []
    latest_map = _latest_policy_rules(db, [link.id for link in policy_links])
    snapshots: list[PolicyRuleSnapshot] = []
    for link in policy_links:
        rule = latest_map.get(link.id)
        snapshots.append(
            PolicyRuleSnapshot(
                policy_link_id=link.id,
                extracted_at=rule.extracted_at if rule else None,
                rules_json=_parse_rules_json(rule.rules_json) if rule else None,
            )
        )
    return snapshots


def build_claim_requirements(db: Session, claim: Claim) -> tuple[dict[str, Any], list[PolicyLink], list[PolicyRuleSnapshot]]:
    mcp_codes = (
        db.execute(select(ClaimMcpCode.mcp_code).where(ClaimMcpCode.claim_id == claim.id))
        .scalars()
        .all()
    )
    diagnosis_codes = (
        db.execute(
            select(ClaimDiagnosisCode.diagnosis_code).where(
                ClaimDiagnosisCode.claim_id == claim.id
            )
        )
        .scalars()
        .all()
    )

    policy_links = get_policy_links_for_claim(db, claim, mcp_codes)
    policy_rules = build_policy_rule_snapshots(db, policy_links)

    requirements: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add_requirement(
        key: str,
        *,
        source: str,
        severity: str,
        reason: str,
        question: str,
        is_missing: bool,
    ) -> None:
        requirements.append(
            {
                "key": key,
                "source": source,
                "severity": severity,
                "reason": reason,
            }
        )
        if is_missing:
            missing.append({"key": key, "question": question})

    patient = claim.patient
    add_requirement(
        "patient.first_name",
        source="base",
        severity="required",
        reason="Patient first name is required.",
        question="Enter patient first name",
        is_missing=not bool(patient.first_name),
    )
    add_requirement(
        "patient.last_name",
        source="base",
        severity="required",
        reason="Patient last name is required.",
        question="Enter patient last name",
        is_missing=not bool(patient.last_name),
    )
    add_requirement(
        "insurance_company_id",
        source="base",
        severity="required",
        reason="Insurance company is required.",
        question="Select insurance company",
        is_missing=not bool(claim.insurance_company_id),
    )
    add_requirement(
        "service_date",
        source="base",
        severity="required",
        reason="Service date is required.",
        question="Enter service date",
        is_missing=claim.service_date is None,
    )
    add_requirement(
        "mcp_codes",
        source="base",
        severity="required",
        reason="At least one procedure code is required.",
        question="Add at least one procedure (MCP) code",
        is_missing=len(mcp_codes) == 0,
    )

    policy_flags = _detect_policy_flags([item.rules_json for item in policy_rules])

    if policy_flags["requires_diagnosis"]:
        add_requirement(
            "diagnosis_codes",
            source="policy",
            severity="required",
            reason="Policy requires diagnosis codes.",
            question="Add at least one diagnosis code",
            is_missing=len(diagnosis_codes) == 0,
        )

    facts = (
        db.execute(
            select(ClaimProcedureFact).where(ClaimProcedureFact.claim_id == claim.id)
        )
        .scalars()
        .all()
    )
    has_pos = any(fact.pos for fact in facts)
    has_units = any(fact.units for fact in facts)
    has_modifier = any(fact.modifier for fact in facts)

    if policy_flags["requires_pos"]:
        add_requirement(
            "place_of_service",
            source="policy",
            severity="required",
            reason="Policy requires place of service.",
            question="Provide place of service (POS)",
            is_missing=not has_pos,
        )
    if policy_flags["requires_units"]:
        add_requirement(
            "units",
            source="policy",
            severity="required",
            reason="Policy requires units.",
            question="Provide units for each procedure",
            is_missing=not has_units,
        )
    if policy_flags["requires_modifier"]:
        add_requirement(
            "modifier",
            source="policy",
            severity="required",
            reason="Policy requires modifiers.",
            question="Provide required modifiers",
            is_missing=not has_modifier,
        )
    if policy_flags["requires_prior_auth"]:
        add_requirement(
            "prior_authorization",
            source="policy",
            severity="required",
            reason="Policy requires prior authorization.",
            question="Provide prior authorization details",
            is_missing=True,
        )

    is_complete = len(missing) == 0

    return (
        {
            "claim_id": claim.id,
            "required_fields": requirements,
            "missing": missing,
            "is_complete": is_complete,
        },
        policy_links,
        policy_rules,
    )
