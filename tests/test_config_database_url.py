from app.core.config import Settings, normalize_database_url


def test_normalize_database_url_rewrites_common_postgres_driver_aliases() -> None:
    assert (
        normalize_database_url("postgresql+psycopg2://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )
    assert (
        normalize_database_url("postgresql://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )
    assert (
        normalize_database_url("postgres://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )


def test_settings_normalize_database_url_before_engine_use() -> None:
    settings = Settings(DATABASE_URL="postgresql+psycopg2://user:pass@db:5432/app")
    assert settings.database_url == "postgresql+psycopg://user:pass@db:5432/app"
