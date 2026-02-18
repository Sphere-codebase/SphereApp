from fastapi.testclient import TestClient
from tenacity import RetryError

from app.api.routes.chat import get_llm_client
from app.core.security import create_access_token
from app.db.id_utils import next_id
from app.db.models import User
from app.db.session import get_db
from app.llm.client import LLMUnavailable
from app.main import app
from app.utils.time import utcnow


class FakeRetryErrorLLM:
    def chat_complete(self, messages, tools=None, temperature=None):
        raise RetryError(None)


@app.get("/__test__/llm-unavailable")
def llm_unavailable() -> None:
    raise LLMUnavailable("unreachable")


def test_llm_unavailable_maps_to_503() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__test__/llm-unavailable")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "LLM_UNAVAILABLE"
    assert payload["error"]["message"] == "LLM service is unavailable"


def test_chat_retry_error_maps_to_503(db_session) -> None:
    user = User(
        id=next_id(db_session, User),
        email="doctor@example.com",
        password_hash="hash",
        is_active=True,
        clinic_id=1,
        created_at=utcnow(),
    )
    db_session.add(user)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_llm_client():
        return FakeRetryErrorLLM()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app, raise_server_exceptions=False)
    try:
        token = create_access_token(str(user.id))
        response = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "hello"},
        )
        assert response.status_code == 503
        payload = response.json()
        assert payload["error"]["code"] == "LLM_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()
