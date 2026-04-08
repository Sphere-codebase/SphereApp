# SphereApp

FastAPI service with Postgres + Alembic migrations and optional local LLM (LM Studio).

## Requirements
- Python 3.12
- Docker (for Postgres)
- (Optional) LM Studio for local LLM server

## Makefile quick commands

This repo includes a `Makefile` that wraps the most common dev commands.

### Quickstart (backend)

```bash
make install
```

| Command | Description |
| :--- | :--- |
| `make start` | Full backend bootstrap (Migrate -> Run) |
| `make migrate` | Run Alembic migrations |
| `make run` | Run API with reload (dev) |

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
# DB pool defaults (recommended)
export DB_POOL_SIZE="10"
export DB_MAX_OVERFLOW="20"
export DB_POOL_TIMEOUT="30"
export DB_POOL_RECYCLE="1800"
export DB_POOL_PRE_PING="true"
# Optional: readiness should not depend on LLM during local debugging
export READY_CHECK_LLM="false"
# Optional: cache /ready DB probe result to avoid burst amplification
export READY_DB_CACHE_TTL_SECONDS="2"
# Optional: read-response caches for remote DB latency mitigation
export AUTH_ME_CACHE_TTL_SECONDS="60"
export ADMIN_REF_CACHE_TTL_SECONDS="300"
export CHAT_SESSIONS_CACHE_TTL_SECONDS="5"
# Optional: policy parser integration
export PARSER_MODE="local"
export PARSER_BASE_URL="http://localhost:8001"
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

## Deploy to Vercel

This repo is ready for Vercel Python Serverless Functions via `api/index.py`. All paths route to the
FastAPI app so `/docs` and `/openapi.json` work by default.

### Required environment variables (Vercel)
- `DATABASE_URL` (Postgres connection string)
- `JWT_SECRET`
- `ENV=prod` (recommended; defaults to `prod` automatically on Vercel)

### Common optional environment variables
- `ADMIN_API_KEY` (needed to bootstrap admins)
- `CORS_ORIGINS` (comma-separated or JSON array)
- `LMSTUDIO_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_STEPS`, `LLM_TEMPERATURE`
- `READY_CHECK_LLM` (set `false` to avoid readiness blocking on LLM)
- `DB_POOL_SIZE` (default `10`)
- `DB_MAX_OVERFLOW` (default `20`)
- `DB_POOL_TIMEOUT` (default `30`)
- `DB_POOL_RECYCLE` (default `1800`)
- `DB_POOL_PRE_PING` (default `true`)
- `READY_DB_CACHE_TTL_SECONDS` (default `2`)
- `AUTH_ME_CACHE_TTL_SECONDS` (default `60`)
- `ADMIN_REF_CACHE_TTL_SECONDS` (default `300`)
- `CHAT_SESSIONS_CACHE_TTL_SECONDS` (default `5`)
- `PARSER_MODE`, `PARSER_BASE_URL`
- `CHAT_FILE_LOGS=false` (recommended for serverless; defaults to disabled in `ENV=prod`)

### Notes for serverless
- The SQLAlchemy engine is created with `create_engine(...)` and opens a connection on first use;
  use a managed Postgres or pooler if you see connection churn on cold starts.
- Vercel/serverless startup no longer writes to the repo filesystem; structured chat/performance
  logs go to stdout so failures are visible in function logs.
- Claim PDFs are generated on demand for `/api/files/pdfs/{filename}` instead of relying on local
  persistent disk, which is not durable across serverless invocations.

### Dev vs prod latency expectations (remote DB)
- If your app runs locally and Postgres is remote (for example Supabase in another region), each DB round-trip can cost hundreds of milliseconds and fresh connects can exceed a second.
- In this setup, endpoint latency is dominated by SQL statement count, not CPU time. Prefer fewer queries and short TTL response caching for read-heavy GET routes.
- In production where app and DB are co-located, round-trip cost drops and cache TTLs can usually be shorter. Set any cache TTL to `0` to disable that cache immediately.

## Policy Parser Integration
- The PDF parser lives under `app/parsers/pdf/` (`pdf_parse.py` + `aetna_eob.py`).
- The backend policy adapter is `app/parsers/policy/aetna_policy.py` and imports `dlc_modul` parser modules when `PARSER_MODE=local`.
- Set `PARSER_MODE=http` to call the external parser service at `PARSER_BASE_URL` (`/api/policy/parse`).

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

## Admin policy rules
- Navigate to `/app/admin` and open the "Companies & Policies" tab.
- In the Policy Links table:
  - Use "Refresh Rules" to parse and review extracted rules. Confirm to store.
  - Use "View Rules" to open the policy rules page.
- On the policy rules page:
  - Pick an MCP code to browse related policy links.
  - Select a policy link to see the latest title, next review date, medical necessity
    text, criteria hierarchy, and notes.
  - If no rules have been parsed yet, the page shows a "No rules parsed yet" message.

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
.venv/bin/python -m compileall app
.venv/bin/ruff check app || true
.venv/bin/pytest -q tests/test_claim_ingest_idempotent.py --maxfail=1 || true
```

Full suite (optional): `.venv/bin/pytest -q`

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
