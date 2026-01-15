import logging
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.chat import get_chat_orchestrator
from app.core.config import settings
from app.core.logging import CHAT_LOGGER_NAME, chat_log_path, configure_logging, log_chat_event
from app.db.models import User
from app.main import app
from app.services.chat_orchestrator import ChatResult


class FakeOrchestrator:
    def __init__(self, user: User) -> None:
        self.user = user

    def run(self, message, session_id):  # noqa: D401
        session = session_id or 1
        return ChatResult(
            session_id=session,
            assistant_message="OK",
            ui_actions=[],
            debug=None,
            action_required=False,
            proposed_changes=None,
        )


def test_chat_file_logs_created_and_redacted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "dev")
    monkeypatch.setattr(settings, "chat_file_logs", True)
    monkeypatch.setattr(settings, "chat_log_dir", str(tmp_path))

    configure_logging(settings.log_level)

    user = User(
        id=1,
        email="doctor@example.com",
        password_hash="hash",
        is_active=True,
    )

    def override_orchestrator():
        return FakeOrchestrator(user)

    app.dependency_overrides[get_chat_orchestrator] = override_orchestrator
    client = TestClient(app)
    try:
        response = client.post(
            "/chat",
            json={"message": "password=secret token=abc123"},
            headers={"X-Request-ID": "req-123"},
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        log_chat_event(
            "chat_request",
            {
                "request_id": "req-123",
                "chat_session_id": session_id,
                "message": "password=secret token=abc123",
            },
        )

        log_path = chat_log_path()
        assert log_path is not None
        assert log_path.exists()

        logger = logging.getLogger(CHAT_LOGGER_NAME)
        handler_paths = [
            getattr(handler, "baseFilename", None) for handler in logger.handlers
        ]
        handler_paths = [path for path in handler_paths if path]
        assert handler_paths
        contents = ""
        for path in handler_paths:
            contents += Path(path).read_text()
        assert "req-123" in contents
        assert "chat_session_id" in contents
        assert "secret" not in contents
        assert "abc123" not in contents
    finally:
        app.dependency_overrides.clear()
