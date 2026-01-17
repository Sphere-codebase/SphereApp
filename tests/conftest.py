import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker


def _create_database(admin_url: str, db_name: str) -> None:
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    finally:
        engine.dispose()


def _drop_database(admin_url: str, db_name: str) -> None:
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db_name"
                ),
                {"db_name": db_name},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    finally:
        engine.dispose()


@pytest.fixture()
def db_session() -> Session:
    admin_url = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
    db_name = f"claims_test_{uuid.uuid4().hex}"
    test_url = make_url(admin_url).set(database=db_name)

    try:
        _create_database(admin_url, db_name)
    except OperationalError as exc:
        pytest.skip(f"Postgres not available: {exc}")

    test_url_str = test_url.render_as_string(hide_password=False)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", test_url_str)
    command.upgrade(config, "head")

    engine = sa.create_engine(test_url_str)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        _drop_database(admin_url, db_name)


def pytest_configure() -> None:
    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("CORS_ORIGINS", "[]")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/claims_assistant",
    )
    os.environ["TEST_ADMIN_DATABASE_URL"] = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
    )
    os.environ.setdefault("PDF_PARSER_MODE", "sample")


@pytest.fixture(autouse=True, scope="session")
def _set_test_env() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("CORS_ORIGINS", "[]")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/claims_assistant",
    )
    monkeypatch.setenv(
        "TEST_ADMIN_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres",
    )
    monkeypatch.setenv("PDF_PARSER_MODE", "sample")
    yield
    monkeypatch.undo()
