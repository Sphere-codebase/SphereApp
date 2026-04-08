import logging
from logging.handlers import RotatingFileHandler

import app.core.performance_logging as performance_logging_module
from app.core.config import Settings, settings
from app.core.logging import CHAT_LOGGER_NAME, chat_log_path, configure_logging
from app.core.performance_logging import PERFORMANCE_LOGGER_NAME, configure_performance_logging


def _reset_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    return logger


def test_settings_default_to_prod_on_vercel(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("ENV", raising=False)

    runtime_settings = Settings()

    assert runtime_settings.env == "prod"
    assert runtime_settings.is_vercel is True
    assert runtime_settings.is_serverless is True


def test_serverless_logging_uses_stdout(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "chat_file_logs", None)
    monkeypatch.setattr(settings, "chat_log_dir", str(tmp_path / "logs"))

    chat_logger = _reset_logger(CHAT_LOGGER_NAME)
    performance_logger = _reset_logger(PERFORMANCE_LOGGER_NAME)
    monkeypatch.setattr(performance_logging_module, "_performance_configured", False)

    configure_logging(settings.log_level)
    configure_performance_logging()

    assert chat_log_path() is None
    assert chat_logger.handlers
    assert all(not hasattr(handler, "baseFilename") for handler in chat_logger.handlers)
    assert performance_logger.handlers
    assert not any(
        isinstance(handler, RotatingFileHandler) for handler in performance_logger.handlers
    )
