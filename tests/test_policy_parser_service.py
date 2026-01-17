import json
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import InsuranceCompany, McpCode, PolicyLink, PolicyRule
from app.parsers.policy.aetna_policy import ParsedPolicy
from app.services.policy import rules_refresh as policy_rules
from app.utils.time import utcnow

SOURCE_URL = "https://www.aetna.com/cpb/medical/data/700_799/0722.html"
TITLE = "Transforaminal Epidural Injections - Medical Clinical Policy Bulletins | Aetna"
MEDICAL_NECESSITY = "Aetna considers transforaminal epidural injections medically necessary ..."


def _seed_policy_link(db_session: Session) -> PolicyLink:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    code = McpCode(code="12345", description="Test Code")
    link = PolicyLink(
        id=next_id(db_session, PolicyLink),
        insurance_company_id=company.id,
        mcp_code=code.code,
        policy_url=SOURCE_URL,
        created_at=utcnow(),
    )
    db_session.add_all([company, code, link])
    db_session.commit()
    return link


def _fake_parsed() -> ParsedPolicy:
    return ParsedPolicy(
        payer_code="aetna",
        source_url=SOURCE_URL,
        title=TITLE,
        next_review_iso=date(2026, 8, 13),
        medical_necessity_clean=MEDICAL_NECESSITY,
        structured={
            "criteria": [{"id": "MN-1", "level": 0, "text": "Criterion", "children": []}],
            "notes": [{"text": "Note text"}],
        },
    )


def test_parse_policy_link_confirm_gate(db_session: Session, monkeypatch) -> None:
    link = _seed_policy_link(db_session)
    parsed = _fake_parsed()

    def fake_parse_policy(url: str, payer_code: str) -> ParsedPolicy:
        return parsed

    monkeypatch.setattr(policy_rules, "parse_policy", fake_parse_policy)

    result = policy_rules.parse_policy_link_and_store(
        policy_link_id=link.id,
        confirm=False,
        db=db_session,
    )

    assert result["action_required"] is True
    assert result["proposed_changes"]["title"] == parsed.title
    assert result["proposed_changes"]["criteria_count"] == 1
    assert result["proposed_changes"]["notes_count"] == 1

    stored = db_session.execute(select(PolicyRule)).scalars().all()
    assert stored == []


def test_parse_policy_link_store(db_session: Session, monkeypatch) -> None:
    link = _seed_policy_link(db_session)
    parsed = _fake_parsed()

    def fake_parse_policy(url: str, payer_code: str) -> ParsedPolicy:
        return parsed

    monkeypatch.setattr(policy_rules, "parse_policy", fake_parse_policy)

    result = policy_rules.parse_policy_link_and_store(
        policy_link_id=link.id,
        confirm=True,
        db=db_session,
    )

    assert result["status"] == "stored"
    stored = db_session.execute(select(PolicyRule)).scalars().all()
    assert len(stored) == 1
    rule = stored[0]
    assert rule.policy_link_id == link.id
    assert rule.title == parsed.title
    assert rule.next_review_iso == parsed.next_review_iso
    assert rule.criteria_json == parsed.structured["criteria"]
    assert rule.notes_json == parsed.structured["notes"]
    assert json.loads(rule.rules_json)["medical_necessity_clean"] == parsed.medical_necessity_clean


def test_parse_policy_link_parser_error(db_session: Session, monkeypatch) -> None:
    link = _seed_policy_link(db_session)

    def fake_parse_policy(url: str, payer_code: str) -> ParsedPolicy:
        raise HTTPException(status_code=504, detail="timeout")

    monkeypatch.setattr(policy_rules, "parse_policy", fake_parse_policy)

    with pytest.raises(HTTPException) as exc:
        policy_rules.parse_policy_link_and_store(
            policy_link_id=link.id,
            confirm=True,
            db=db_session,
        )

    assert exc.value.status_code == 504
    assert "timeout" in str(exc.value.detail)
