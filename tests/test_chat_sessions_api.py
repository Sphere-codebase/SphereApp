import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models import Agency, ChatSession, Claim, ClaimStatus, Patient, Tenant, User
from app.db.session import get_db
from app.main import app


def _seed_user(db_session: Session, name: str) -> User:
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {name}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"doctor-{name.lower()}@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    db_session.add_all([tenant, user])
    db_session.commit()
    return user


def test_list_sessions_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/sessions")

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_list_sessions_scoped_to_user(db_session: Session) -> None:
    user_a = _seed_user(db_session, "A")
    user_b = _seed_user(db_session, "B")

    session_a1 = ChatSession(tenant_id=user_a.tenant_id, user_id=user_a.id)
    session_a2 = ChatSession(tenant_id=user_a.tenant_id, user_id=user_a.id)
    session_b = ChatSession(tenant_id=user_b.tenant_id, user_id=user_b.id)
    db_session.add_all([session_a1, session_a2, session_b])
    db_session.commit()

    token = create_access_token(str(user_a.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/chat/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        returned_ids = {item["id"] for item in payload}
        assert returned_ids == {str(session_a1.id), str(session_a2.id)}
    finally:
        app.dependency_overrides.clear()


def test_create_session_requires_auth() -> None:
    client = TestClient(app)
    response = client.post("/api/chat/sessions", json={})

    assert response.status_code == 401
    assert response.headers.get("X-Request-ID") is not None


def test_create_session_success(db_session: Session) -> None:
    user = _seed_user(db_session, "Create")
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/chat/sessions",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["claim_id"] is None

        created = db_session.get(ChatSession, uuid.UUID(payload["id"]))
        assert created is not None
        assert created.user_id == user.id
        assert created.tenant_id == user.tenant_id
    finally:
        app.dependency_overrides.clear()


def test_create_session_cross_tenant_claim_returns_404(db_session: Session) -> None:
    user = _seed_user(db_session, "Owner")
    other_tenant = Tenant(id=uuid.uuid4(), name="Tenant Other")
    other_user = User(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        email="doctor-other@example.com",
        hashed_password=get_password_hash("secret"),
        is_active=True,
    )
    agency = Agency(id=uuid.uuid4(), name="Agency Other", slug="agency-other", is_active=True)
    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        user_id=other_user.id,
        first_name="Jane",
        last_name="Roe",
        full_name="Jane Roe",
    )
    claim = Claim(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        agency_id=agency.id,
        patient_id=patient.id,
        status=ClaimStatus.DRAFT,
    )
    db_session.add_all([other_tenant, other_user, agency, patient, claim])
    db_session.commit()

    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/chat/sessions",
            json={"claim_id": str(claim.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404
        assert response.headers.get("X-Request-ID") is not None
        count = db_session.execute(
            select(ChatSession).where(ChatSession.user_id == user.id)
        ).scalars()
        assert count.first() is None
    finally:
        app.dependency_overrides.clear()


def test_get_session_returns_200(db_session: Session) -> None:
    user = _seed_user(db_session, "Get")
    session = ChatSession(tenant_id=user.tenant_id, user_id=user.id)
    db_session.add(session)
    db_session.commit()
    token = create_access_token(str(user.id))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/chat/sessions/{session.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == str(session.id)
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_not_found_regression(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 401
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()
