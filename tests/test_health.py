from fastapi.testclient import TestClient

from app.api.routes.health import get_llm_client
from app.core.config import settings
from app.db.session import get_db
from app.llm.client import LLMUnavailable
from app.main import app


class FakeLLMClient:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    def health_check(self) -> None:
        if self.should_fail:
            raise LLMUnavailable("down")


def test_health_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_ready_ok(db_session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get("/ready")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_ready_llm_unavailable(db_session) -> None:
    def override_get_db():
        yield db_session

    def override_llm_client():
        return FakeLLMClient(should_fail=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    original = settings.ready_check_llm
    settings.ready_check_llm = True
    client = TestClient(app)
    try:
        response = client.get("/ready")
        assert response.status_code == 503
    finally:
        settings.ready_check_llm = original
        app.dependency_overrides.clear()
