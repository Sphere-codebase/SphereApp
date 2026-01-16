# SphereApp

FastAPI service with Postgres + Alembic migrations and optional local LLM (LM Studio).

## Requirements
- Python 3.11
- Docker (for Postgres)
- (Optional) LM Studio for local LLM server

## Makefile quick commands

This repo includes a `Makefile` that wraps the most common dev commands.

### Quickstart (backend)

```bash
make install
make start
```

What `make start` does: `db-up` (Postgres) → `db-upgrade` (Alembic) → `run` (Uvicorn with reload).

### Useful targets

```bash
make help            # list all targets

make venv            # create .venv
make install         # install backend deps (incl dev)

make db-up           # start Postgres (docker compose)
make db-down         # stop Postgres
make db-logs         # follow Postgres logs
make db-wait         # wait for postgres health
make db-upgrade      # run Alembic migrations against compose DB
make db-dump         # dump data to backups/ directory
make db-restore      # restore data from SQL file (requires FILE=...)

make run             # run API (reload)
make run-prod        # run API (no reload)

make test            # run tests
make fmt             # ruff format
make lint            # ruff lint
make type            # mypy
make ci              # CI-like: fmt-check + lint + migrate + test
```

### Frontend targets

```bash
make frontend-install
make frontend-dev
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Local run

If you prefer, you can use `make start` (see above). Manual steps are below.

### 1) Start Postgres
```bash
docker compose up -d
```

Makefile equivalent:

```bash
make db-up
```

### 2) Set env
Create .env (or export vars in your shell). Minimum:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant"
export JWT_SECRET="dev-secret"
export ENV="dev"
# Optional: readiness should not depend on LLM during local debugging
export READY_CHECK_LLM="false"
```

### 3) Run migrations
```bash
python -m alembic upgrade head
```

Makefile equivalent:

```bash
make db-upgrade
```

### 4) Start API
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Makefile equivalent:

```bash
make run
```

### 5) Health checks
```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
```

## Creating an Admin User

To create a new user with admin privileges, you must use the `ADMIN_API_KEY` backdoor.

### 1. Configure Admin Key
Ensure your `.env` file (or environment) has the `ADMIN_API_KEY` variable set.

```bash
# .env
# Example (development only):
ADMIN_API_KEY=5b241278440774e6c74d3019bb74f2585d8762b4d66134d17db66b723c8c6709013afc738ef5fa60b685f2bbabd143595dc7751ffb829259041b4526b2d42098
```

### 2. Create the Admin (or User)
With the server running (e.g., via `make run`), you can use the `create-admin` or `create-user` make targets. They will automatically pick up `ADMIN_API_KEY` from your `.env`.

**Create an Admin:**
```bash
make create-admin EMAIL=admin@example.com PASSWORD=strong_password FULL_NAME="System Admin"
```

**Create a Standard User:**
```bash
make create-user EMAIL=doctor@example.com PASSWORD=secret
```

_Note: If you don't use `.env`, you can pass the key manually:_
```bash
make create-admin ADMIN_API_KEY=secret-key ...
```

### 3. Verify
The make command will output the JSON response containing the access token. You can verify login:

```bash
# Verify login
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"strong_password"}'
```

## Auth quickstart

Create user (admin-only):

```bash
export ADMIN_API_KEY="dev-admin-key"
curl -s -X POST http://localhost:8000/auth/admin/users \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: dev-admin-key" \
  -d '{"email":"doc1@example.com","password":"secret"}'; echo
```

Login:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doc1@example.com","password":"secret"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "$TOKEN"
```

Me:

```bash
curl -i http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: me-1"
```

## Chat

Minimal chat:

```bash
curl -i -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: chat-1" \
  -d '{"message":"Say exactly OK"}'; echo
```

Continue a session:

```bash
SESSION_ID="<paste from previous response>"
curl -i -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: chat-2" \
  -d "{\"session_id\":\"$SESSION_ID\",\"message\":\"What did I just ask you to say? Answer in one word.\"}"; echo
```

## LM Studio (optional)

Run LM Studio server on your LLM machine, e.g.:

- Same machine: `http://127.0.0.1:1234/v1`
- Another machine on the same Wi-Fi: `http://<LM_IP>:1234/v1`

Then set:

```bash
export LLM_BASE_URL="http://<LM_IP>:1234/v1"
```

## Tests
```bash
make test
```

(Direct: `.venv/bin/pytest -q`)

## CI
GitHub Actions workflow:

- starts Postgres as a service
- runs Alembic migrations and tests
- builds Docker image
- smoke-tests /health and /ready on port 8000

Local CI-like checks:

```bash
make ci
```

Local Docker smoke (build + run + health/ready + stop):

```bash
make docker-ci
```

## Database Backups

You can dump the local Docker-based database to the `backups/` directory:

```bash
make db-dump
```

To restore from a dump, specify the file path:

```bash
make db-restore FILE=backups/dump_20230101_120000.sql
```

_(Note: This drops/recreates data depending on the dump content, use with caution.)_

---

If you want next steps:
- add CI badge to README
- split CI into jobs (lint / test / docker-smoke)
- prepare a separate `docker-compose.ci.yml`
