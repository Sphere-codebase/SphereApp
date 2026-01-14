from pathlib import Path


def test_chat_payload_helper_includes_session_id() -> None:
    contents = Path("static/js/chat_helpers.js").read_text()
    assert "function buildChatPayload" in contents
    assert "session_id" in contents


def test_chat_frontend_log_cooldown_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "frontendLogCooldownKey" in contents
    assert "response.status === 429" in contents


def test_chat_frontend_debug_logger_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "function logEvent" in contents
    assert "console.debug" in contents
    assert "frontend_debug_log_buffer" in contents


def test_chat_fetch_handles_no_content() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "response.status === 204" in contents


def test_chat_init_guard_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "__chatAppInitialized" in contents


def test_chat_session_active_ui_helper_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "function updateSessionActiveUI" in contents


def test_chat_log_allowlist_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "chatLogEventAllowlist" in contents
    assert "\"chat_request\"" in contents


def test_chat_refresh_schedule_present() -> None:
    contents = Path("static/js/chat.js").read_text()
    assert "function scheduleRefreshMessages" in contents
