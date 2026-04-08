#!/usr/bin/env sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

DATABASE_URL="$(DATABASE_URL="$DATABASE_URL" python - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

url = os.environ["DATABASE_URL"].strip()
if url.startswith("postgres://"):
    url = f"postgresql+psycopg://{url[len('postgres://'):]}"
elif url.startswith("postgresql://"):
    url = f"postgresql+psycopg://{url[len('postgresql://'):]}"
elif url.startswith("postgresql+psycopg2://"):
    url = f"postgresql+psycopg://{url[len('postgresql+psycopg2://'):]}"

parts = urlsplit(url)
if parts.hostname in {"localhost", "127.0.0.1"}:
    netloc = parts.netloc.replace(parts.hostname, "host.docker.internal", 1)
    url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

print(url)
PY
)"
export DATABASE_URL

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
