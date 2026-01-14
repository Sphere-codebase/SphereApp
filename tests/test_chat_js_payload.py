from pathlib import Path


def test_chat_payload_helper_includes_session_id() -> None:
    contents = Path("static/js/chat_helpers.js").read_text()
    assert "function buildChatPayload" in contents
    assert "session_id" in contents


def test_chat_frontend_log_cooldown_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "frontendLogCooldownKey" in contents
    assert "response.status === 429" in contents
