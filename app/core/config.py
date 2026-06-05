"""Application configuration via environment variables."""

from __future__ import annotations

import json
import os
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


def _truthy_env(name: str) -> bool:
    value = os.getenv(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_vercel_runtime_env() -> bool:
    return _truthy_env("VERCEL") or bool(os.getenv("VERCEL_ENV")) or bool(os.getenv("VERCEL_URL"))


def _default_runtime_env() -> Literal["dev", "test", "prod"]:
    if _is_vercel_runtime_env():
        return "prod"
    return "dev"


def _looks_local_address(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ("localhost", "127.0.0.1", "0.0.0.0"))


def normalize_database_url(value: object) -> object:
    if not isinstance(value, str):
        return value
    url = value.strip()
    if url.startswith("postgres://"):
        return f"postgresql+psycopg://{url[len('postgres://') :]}"
    if url.startswith("postgresql://"):
        return f"postgresql+psycopg://{url[len('postgresql://') :]}"
    if url.startswith("postgresql+psycopg2://"):
        return f"postgresql+psycopg://{url[len('postgresql+psycopg2://') :]}"
    return url


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
    db_pool_size: int = Field(10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(20, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(1800, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(True, alias="DB_POOL_PRE_PING")

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
    ready_db_cache_ttl_seconds: float = Field(2.0, alias="READY_DB_CACHE_TTL_SECONDS")
    auth_me_cache_ttl_seconds: float = Field(60.0, alias="AUTH_ME_CACHE_TTL_SECONDS")
    admin_ref_cache_ttl_seconds: float = Field(300.0, alias="ADMIN_REF_CACHE_TTL_SECONDS")
    chat_sessions_cache_ttl_seconds: float = Field(5.0, alias="CHAT_SESSIONS_CACHE_TTL_SECONDS")

    pdf_parser_url: str = Field("http://localhost:8001", alias="PDF_PARSER_URL")
    pdf_parser_api_key: str = Field("default_secret", alias="PDF_PARSER_API_KEY")
    pdf_parser_max_size_bytes: int = Field(25 * 1024 * 1024, alias="PDF_PARSER_MAX_SIZE_BYTES")
    pdf_parser_timeout_seconds: float = Field(60.0, alias="PDF_PARSER_TIMEOUT_SECONDS")
    pdf_parser_retries: int = Field(3, alias="PDF_PARSER_RETRIES")

    stedi_api_key: str | None = Field(None, alias="STEDI_API_KEY")
    stedi_base_url: str = Field(
        "https://healthcare.us.stedi.com/2024-04-01",
        alias="STEDI_BASE_URL",
    )
    stedi_timeout_seconds: float = Field(60.0, alias="STEDI_TIMEOUT_SECONDS")
    stedi_enabled: bool = Field(False, alias="STEDI_ENABLED")
    stedi_provider_npi: str | None = Field(None, alias="STEDI_PROVIDER_NPI")
    stedi_provider_tax_id: str | None = Field(None, alias="STEDI_PROVIDER_TAX_ID")
    stedi_provider_organization_name: str | None = Field(
        None,
        alias="STEDI_PROVIDER_ORGANIZATION_NAME",
    )

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

    @field_validator("env", mode="before")
    @classmethod
    def parse_env(cls, value: object) -> object:
        if (value is None or value == "dev") and os.getenv("ENV") is None:
            return _default_runtime_env()
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, value: object) -> object:
        return normalize_database_url(value)

    @property
    def is_vercel(self) -> bool:
        return _is_vercel_runtime_env()

    @property
    def is_serverless(self) -> bool:
        return self.is_vercel or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.env != "prod":
            return warnings

        if self.jwt_secret == "change-me":
            warnings.append("JWT_SECRET is using the default insecure value.")
        if _looks_local_address(self.database_url):
            warnings.append("DATABASE_URL points to a local host and will fail on Vercel.")
        if self.ready_check_llm and _looks_local_address(self.lmstudio_base_url):
            warnings.append(
                "READY_CHECK_LLM is enabled but LMSTUDIO_BASE_URL points to a local host."
            )
        if _looks_local_address(self.pdf_parser_url):
            warnings.append("PDF_PARSER_URL points to a local host.")
        return warnings


settings = Settings()  # type: ignore[call-arg]
