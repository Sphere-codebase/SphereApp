"""Policy rule parsing and storage helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import InsuranceCompany, PolicyLink, PolicyRule
from app.db.session import SessionLocal
from app.parsers.policy.aetna_policy import parse_policy
from app.utils.time import utcnow


def _preview(text: str, limit: int = 200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


_PAYER_CODE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_payer_code(name: str) -> str:
    cleaned = _PAYER_CODE_RE.sub("_", name.strip().lower())
    return cleaned.strip("_")


def parse_policy_link_and_store(
    policy_link_id: int,
    confirm: bool,
    payer_code: str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        link = db.execute(
            select(PolicyLink).where(PolicyLink.id == policy_link_id)
        ).scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy link not found",
            )

        payer = payer_code
        if payer is None or not payer.strip():
            company = db.get(InsuranceCompany, link.insurance_company_id)
            if company is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Insurance company not found",
                )
            payer = _normalize_payer_code(company.name)
        parsed = parse_policy(url=link.policy_url, payer_code=payer)
        structured = parsed.structured if isinstance(parsed.structured, dict) else {}
        criteria = _safe_list(structured.get("criteria"))
        notes = _safe_list(structured.get("notes"))

        proposed = {
            "title": parsed.title,
            "next_review_iso": parsed.next_review_iso.isoformat()
            if parsed.next_review_iso
            else None,
            "criteria_count": len(criteria),
            "notes_count": len(notes),
            "medical_necessity_clean_preview": _preview(parsed.medical_necessity_clean),
        }

        if not confirm:
            return {
                "action_required": True,
                "proposed_changes": proposed,
                "next_action": {
                    "tool": "parse_policy_link_and_store",
                    "args": {
                        "policy_link_id": policy_link_id,
                        "confirm": True,
                    },
                },
            }

        rule = PolicyRule(
            id=next_id(db, PolicyRule),
            policy_link_id=link.id,
            extracted_at=utcnow(),
            title=parsed.title,
            next_review_iso=parsed.next_review_iso,
            criteria_json=criteria,
            notes_json=notes,
            rules_json=json.dumps({"medical_necessity_clean": parsed.medical_necessity_clean}),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

        return {
            "status": "stored",
            "policy_link_id": link.id,
            "policy_rules_id": rule.id,
            "title": parsed.title,
            "next_review_iso": parsed.next_review_iso.isoformat()
            if parsed.next_review_iso
            else None,
            "criteria_count": len(criteria),
            "notes_count": len(notes),
        }
    finally:
        if own_session:
            db.close()
