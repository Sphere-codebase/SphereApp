#!/usr/bin/env sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)

deadline = time.time() + 30
last_err = None
while time.time() < deadline:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except Exception as exc:
        last_err = exc
        time.sleep(1)
else:
    raise SystemExit(f"Database not ready: {last_err}")
PY

python -m alembic -c /app/alembic.ini upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
