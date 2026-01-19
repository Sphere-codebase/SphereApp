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
from app.utils.time import utcnow

client = TestClient(app)


def _seed_admin(db: Session) -> User:
    admin_role = db.execute(select(Role).where(Role.code == "admin")).scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(id=next_id(db, Role), code="admin", description="Admin")
        db.add(admin_role)

    doctor_role = db.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db, Role), code="doctor", description="Doctor")
        db.add(doctor_role)
    db.flush()

    user = User(
        id=next_id(db, User),
        email="admin@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        created_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()
    return user


def _seed_policy_link(db: Session) -> PolicyLink:
    company = InsuranceCompany(id=next_id(db, InsuranceCompany), name="Aetna")
    code = McpCode(code="12345", description="Test Code")
    link = PolicyLink(
        id=next_id(db, PolicyLink),
        insurance_company_id=company.id,
        mcp_code=code.code,
        policy_url="https://example.com/policy",
        created_at=utcnow(),
    )
    db.add_all([company, code, link])
    db.commit()
    return link


def test_openapi_contains_policy_links_rules_route():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()
    paths = openapi.get("paths", {})
    assert "/api/admin/policy-links/{policy_link_id}/rules" in paths


def test_policy_links_rules_404_when_no_rule(db_session: Session):
    user = _seed_admin(db_session)
    link = _seed_policy_link(db_session)
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(
            f"/api/admin/policy-links/{link.id}/rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["details"]["detail"] == "Policy rules not found"
    finally:
        app.dependency_overrides.clear()


def test_policy_links_rules_200_when_rule_exists(db_session: Session):
    user = _seed_admin(db_session)
    link = _seed_policy_link(db_session)
    token = create_access_token(str(user.id))

    rule = PolicyRule(
        id=next_id(db_session, PolicyRule),
        policy_link_id=link.id,
        extracted_at=utcnow(),
        title="Test Policy",
        next_review_iso=date(2026, 1, 1),
        criteria_json=[],
        notes_json=[],
        rules_json=json.dumps({"medical_necessity_clean": "Sample text"}),
    )
    db_session.add(rule)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get(
            f"/api/admin/policy-links/{link.id}/rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["title"] == "Test Policy"
        assert payload["medical_necessity_clean"] == "Sample text"
    finally:
        app.dependency_overrides.clear()
