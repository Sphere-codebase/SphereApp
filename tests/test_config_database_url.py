from app.core.config import Settings, normalize_database_url
from app.db.session import _psycopg_connect_args


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


def test_psycopg_connect_args_disable_prepare_in_dev() -> None:
    args = _psycopg_connect_args("postgresql+psycopg://user:pass@db:5432/app", "dev")
    assert args == {"prepare_threshold": None}


def test_psycopg_connect_args_disable_prepare_for_pooler_in_prod() -> None:
    args = _psycopg_connect_args(
        "postgresql+psycopg://user:pass@aws-0-us-west-2.pooler.supabase.com:6543/postgres",
        "prod",
    )
    assert args == {"prepare_threshold": None}


def test_psycopg_connect_args_keep_prepare_for_direct_prod_connection() -> None:
    args = _psycopg_connect_args("postgresql+psycopg://user:pass@db:5432/app", "prod")
    assert args == {}
