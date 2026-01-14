from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.health import get_llm_client
from app.core.config import settings
from app.db.session import get_db
from app.llm.client import LLMUnavailable
from app.main import app


class UnavailableLLMClient:
    def health_check(self) -> None:
        raise LLMUnavailable("down")


def test_status_payload_has_keys(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") is not None
        payload = response.json()
        assert payload["db_ready"] is True
        assert "llm_ready" in payload
        assert "overall_ready" in payload
        assert "reason" in payload
        assert "checked_at" in payload
        assert payload["env"] == settings.env
        assert payload["llm_model"] == settings.llm_model
        assert payload["lmstudio_base_url"] == settings.lmstudio_base_url
        assert payload["llm_max_steps"] == settings.llm_max_steps
    finally:
        app.dependency_overrides.clear()


def test_status_llm_unavailable(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ready_check_llm", True)

    def override_get_db():
        yield db_session

    def override_llm_client():
        return UnavailableLLMClient()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_llm_client
    client = TestClient(app)
    try:
        response = client.get("/api/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["db_ready"] is True
        assert payload["llm_ready"] is False
        assert payload["overall_ready"] is False
        assert payload["reason"] == "LLM_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "ready_check_llm", False)
