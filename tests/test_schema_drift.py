from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.main import app


def _get_current_revision(db_session: Session) -> str | None:
    result = db_session.execute(text("SELECT version_num FROM alembic_version"))
    row = result.first()
    if row is None:
        return None
    return str(row[0])


def test_schema_matches_models(db_session: Session) -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    current_revision = _get_current_revision(db_session)

    assert head_revision is not None
    assert current_revision == head_revision, (
        "Database schema is not at alembic head. "
        "Run `alembic upgrade head` or `make db-upgrade`."
    )

    inspector = inspect(db_session.get_bind())
    column_names = {column["name"] for column in inspector.get_columns("users")}
    expected_columns = set(User.__table__.columns.keys())
    missing = expected_columns - column_names
    assert not missing, f"Missing columns in users table: {sorted(missing)}"

    db_session.execute(select(User).limit(1)).scalars().all()


def test_login_smoke_does_not_500(db_session: Session) -> None:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "bad"},
        )
        assert response.status_code in {200, 401}
        assert response.headers.get("X-Request-ID") is not None
    finally:
        app.dependency_overrides.clear()
