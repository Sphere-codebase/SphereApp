import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import (
    InsuranceCompany,
    McpCode,
    PolicyLink,
    PolicyRule,
    Role,
    User,
    UserRole,
)
from app.db.session import get_db
from app.main import app
from app.parsers.policy.aetna_policy import ParsedPolicy
from app.services.policy import rules_refresh as policy_rules
from app.utils.time import utcnow


def _seed_user(db_session: Session, is_admin: bool) -> User:
    admin_role = db_session.execute(select(Role).where(Role.code == "admin")).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(id=next_id(db_session, Role), code="admin", description="Admin")
        db_session.add(admin_role)
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
    db_session.flush()

    user = User(
        id=next_id(db_session, User),
        email="admin@example.com" if is_admin else "member@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    if is_admin:
        db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db_session.commit()
    return user


def _seed_policy_link(db_session: Session) -> PolicyLink:
    company = InsuranceCompany(id=next_id(db_session, InsuranceCompany), name="Aetna")
    code = McpCode(code="12345", description="Test Code")
    link = PolicyLink(
        id=next_id(db_session, PolicyLink),
        insurance_company_id=company.id,
        mcp_code=code.code,
        policy_url="https://www.aetna.com/cpb/medical/data/700_799/0722.html",
        created_at=utcnow(),
    )
    db_session.add_all([company, code, link])
    db_session.commit()
    return link


def _fake_parsed() -> ParsedPolicy:
    return ParsedPolicy(
        payer_code="aetna",
        source_url="https://www.aetna.com/cpb/medical/data/700_799/0722.html",
        title="Transforaminal Epidural Injections - Medical Clinical Policy Bulletins | Aetna",
        next_review_iso=date(2026, 8, 13),
        medical_necessity_clean=(
            "Aetna considers transforaminal epidural injections medically necessary ..."
        ),
        structured={
            "criteria": [{"id": "MN-1", "level": 0, "text": "Criterion", "children": []}],
            "notes": [{"text": "Note text"}],
        },
    )


def test_admin_policy_rules_parse_and_store(db_session: Session, monkeypatch) -> None:
    user = _seed_user(db_session, is_admin=True)
    link = _seed_policy_link(db_session)
    token = create_access_token(str(user.id))
    parsed = _fake_parsed()

    def fake_parse_policy(url: str, payer_code: str) -> ParsedPolicy:
        return parsed

    monkeypatch.setattr(policy_rules, "parse_policy", fake_parse_policy)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/admin/policy-links/{link.id}/parse",
            json={"confirm": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["action_required"] is True

        stored = db_session.execute(select(PolicyRule)).scalars().all()
        assert stored == []

        response = client.post(
            f"/api/admin/policy-links/{link.id}/parse",
            json={"confirm": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "stored"

        stored = db_session.execute(select(PolicyRule)).scalars().all()
        assert len(stored) == 1
        rule = stored[0]
        assert rule.policy_link_id == link.id
        assert rule.title == parsed.title
        assert rule.next_review_iso == parsed.next_review_iso
        assert rule.criteria_json == parsed.structured["criteria"]
        assert rule.notes_json == parsed.structured["notes"]
        assert (
            json.loads(rule.rules_json)["medical_necessity_clean"]
            == parsed.medical_necessity_clean
        )
    finally:
        app.dependency_overrides.clear()


def test_admin_policy_rules_read(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=True)
    link = _seed_policy_link(db_session)
    token = create_access_token(str(user.id))
    rule = PolicyRule(
        id=next_id(db_session, PolicyRule),
        policy_link_id=link.id,
        extracted_at=utcnow(),
        title="Policy title",
        next_review_iso=date(2026, 8, 13),
        criteria_json=[{"id": "MN-1", "text": "Criterion", "children": []}],
        notes_json=[{"text": "Note text"}],
        rules_json=json.dumps({"medical_necessity_clean": "Medical necessity text"}),
    )
    db_session.add(rule)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/admin/policy-links/{link.id}/rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["policy_rules_id"] == rule.id
        assert payload["medical_necessity_clean"] == "Medical necessity text"
    finally:
        app.dependency_overrides.clear()


def test_policy_rules_require_admin(db_session: Session) -> None:
    user = _seed_user(db_session, is_admin=False)
    link = _seed_policy_link(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/admin/policy-links/{link.id}/parse",
            json={"confirm": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        response = client.get(
            f"/api/admin/policy-links/{link.id}/rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
