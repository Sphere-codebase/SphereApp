"""Application configuration via environment variables."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _CorsEnvSettingsSource(EnvSettingsSource):
    def decode_complex_value(self, field_name: str, field: Any, value: Any) -> Any:
        if field_name == "cors_origins":
            return value
        return super().decode_complex_value(field_name, field, value)


class _CorsDotEnvSettingsSource(DotEnvSettingsSource):
    def decode_complex_value(self, field_name: str, field: Any, value: Any) -> Any:
        if field_name == "cors_origins":
            return value
        return super().decode_complex_value(field_name, field, value)


class Settings(BaseSettings):
    env: Literal["dev", "test", "prod"] = Field("dev", alias="ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        alias="CORS_ORIGINS",
    )

    lmstudio_base_url: str = Field("http://localhost:1234/v1", alias="LMSTUDIO_BASE_URL")
    llm_model: str = Field("local-model", alias="LLM_MODEL")
    llm_timeout_seconds: int = Field(60, alias="LLM_TIMEOUT_SECONDS")
    llm_max_steps: int = Field(5, alias="LLM_MAX_STEPS")
    llm_temperature: float = Field(0.2, alias="LLM_TEMPERATURE")

    database_url: str = Field(
        "postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant",
        alias="DATABASE_URL",
    )

    jwt_secret: str = Field("change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expires_minutes: int = Field(60, alias="JWT_EXPIRES_MINUTES")
    admin_api_key: str | None = Field(None, alias="ADMIN_API_KEY")
    agent_api_key: str | None = Field(None, alias="AGENT_API_KEY")
    chat_file_logs: bool | None = Field(None, alias="CHAT_FILE_LOGS")
    chat_log_dir: str = Field("logs", alias="CHAT_LOG_DIR")

    max_user_message_chars: int = Field(4000, alias="MAX_USER_MESSAGE_CHARS")
    max_context_chars: int = Field(8000, alias="MAX_CONTEXT_CHARS")
    ready_check_llm: bool = Field(False, alias="READY_CHECK_LLM")

    pdf_parser_url: str = Field("http://localhost:8001", alias="PDF_PARSER_URL")
    pdf_parser_api_key: str = Field("default_secret", alias="PDF_PARSER_API_KEY")
    pdf_parser_max_size_bytes: int = Field(25 * 1024 * 1024, alias="PDF_PARSER_MAX_SIZE_BYTES")
    pdf_parser_timeout_seconds: float = Field(60.0, alias="PDF_PARSER_TIMEOUT_SECONDS")
    pdf_parser_retries: int = Field(3, alias="PDF_PARSER_RETRIES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _CorsEnvSettingsSource(settings_cls),
            _CorsDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed == "":
                return []
            if "*" in trimmed:
                return ["*"]
            if trimmed.startswith("["):
                parsed = cast(list[Any], json.loads(trimmed))
                return [str(item) for item in parsed]
            return [item.strip() for item in trimmed.split(",") if item.strip()]
        raise ValueError("CORS_ORIGINS must be a list or comma-separated string")


settings = Settings()  # type: ignore[call-arg]
