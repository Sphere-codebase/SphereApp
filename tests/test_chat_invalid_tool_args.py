from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token, get_password_hash
from app.db.id_utils import next_id
from app.db.models import ChatMessage, Role, User, UserRole
from app.db.session import get_db
from app.llm.client import ChatCompletionResult, ToolCall
from app.llm.tools import registry as tool_registry
from app.main import app
from app.utils.time import utcnow


class FakeLLMClient:
    def __init__(self, responses: list[ChatCompletionResult]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_complete(self, messages, tools, temperature=None):  # noqa: D401
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _seed_user(db_session: Session) -> User:
    doctor_role = db_session.execute(select(Role).where(Role.code == "doctor")).scalar_one_or_none()
    if doctor_role is None:
        doctor_role = Role(id=next_id(db_session, Role), code="doctor", description="Doctor")
        db_session.add(doctor_role)
        db_session.flush()
    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash=get_password_hash("secret"),
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=doctor_role.id))
    db_session.commit()
    return user


def test_invalid_tool_args(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Try tool",
            tool_calls=[ToolCall(id="call-1", name="get_claim", arguments={"claim_id": "bad"})],
        ),
        ChatCompletionResult(assistant_text="Fallback", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Test invalid args"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assistant_message"] == "Fallback"

        tool_errors = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.content.ilike("%TOOL_VALIDATION_ERROR%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_errors
    finally:
        app.dependency_overrides.clear()


def test_invalid_tool_args_list_procedure_codes(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Try tool",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="list_procedure_codes",
                    arguments={"limit": "bad"},
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Fallback", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Test invalid args"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assistant_message"] == "Fallback"

        tool_errors = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.content.ilike("%list_procedure_codes%"),
                    ChatMessage.content.ilike("%TOOL_VALIDATION_ERROR%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_errors
    finally:
        app.dependency_overrides.clear()


def test_invalid_request_form_args_returns_200(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Need patient id",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="request_form",
                    arguments={"fields": [{}]},
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Please provide the patient ID.", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "List recent claims"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assistant_message"] == "Please provide the patient ID."

        tool_errors = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.content.ilike("%request_form%"),
                    ChatMessage.content.ilike("%TOOL_VALIDATION_ERROR%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_errors
    finally:
        app.dependency_overrides.clear()


def test_unexpected_tool_exception_returns_200(db_session: Session) -> None:
    user = _seed_user(db_session)
    token = create_access_token(str(user.id))
    responses = [
        ChatCompletionResult(
            assistant_text="Try patient search",
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="search_patients",
                    arguments={"query": "Jane"},
                )
            ],
        ),
        ChatCompletionResult(assistant_text="Please provide a patient identifier.", tool_calls=[]),
    ]
    fake_llm = FakeLLMClient(responses)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return fake_llm

    original = tool_registry.TOOLS["search_patients"]

    def _boom(ctx, args):
        raise RuntimeError("boom")

    tool_registry.TOOLS["search_patients"] = tool_registry.ToolDefinition(
        name=original.name,
        description=original.description,
        args_model=original.args_model,
        handler=_boom,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "Find patient"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assistant_message"] == "Please provide a patient identifier."

        tool_errors = (
            db_session.execute(
                select(ChatMessage).where(
                    ChatMessage.content.ilike("%search_patients%"),
                    ChatMessage.content.ilike("%TOOL_EXECUTION_ERROR%"),
                )
            )
            .scalars()
            .all()
        )
        assert tool_errors
    finally:
        tool_registry.TOOLS["search_patients"] = original
        app.dependency_overrides.clear()
