# Claims Assistant (Doctor Helper) — Backend (FastAPI)

This repo is the backend for a multi-tenant doctor assistant that helps manage claims.
It uses a local LLM (LM Studio) with tool use to query/update a database, while enforcing
strict tenant/user isolation and storing audit logs of all interactions.

> This README is a draft skeleton. Codex must complete it during implementation.

---

## Setup
- Python 3.11
- Create venv:
  - `make venv`
- Install dependencies (incl dev):
  - `make install`
- Start database and apply migrations:
  - `docker compose up -d`
  - `make db-upgrade`
- Run API server:
  - `make run`

## Run
- Start database (local Postgres):
  - `docker compose up -d`
- Run API server (reload):
  - `make run`

## Migrations
- Create a new migration:
  - `alembic revision --autogenerate -m "describe change"`
- Apply latest migrations:
  - `alembic upgrade head`

## Env
Create a `.env` from `.env.example` for local dev. Variables:
- `ENV`: `dev`, `test`, or `prod`
- `LOG_LEVEL`: e.g. `INFO`
- `CORS_ORIGINS`: comma-separated list or JSON array
- `LMSTUDIO_BASE_URL`: LM Studio base URL, e.g. `http://localhost:1234/v1`
- `LLM_MODEL`: model name, e.g. `local-model`
- `LLM_TIMEOUT_SECONDS`: request timeout in seconds
- `LLM_MAX_STEPS`: max tool loop steps
- `LLM_TEMPERATURE`: model temperature
- `DATABASE_URL`: Postgres DSN, e.g. `postgresql+psycopg://postgres:postgres@127.0.0.1:5432/claims_assistant`
- `JWT_SECRET`: secret for HS256 JWT signing
- `JWT_ALGORITHM`: e.g. `HS256`
- `JWT_EXPIRES_MINUTES`: token expiry in minutes
- `MAX_USER_MESSAGE_CHARS`: hard limit for user message size
- `MAX_CONTEXT_CHARS`: hard limit for prompt context
- `READY_CHECK_LLM`: when `true`, `/ready` checks LLM availability and returns 503 if unavailable

## API
Planned endpoints:
- `POST /chat`
- `GET /health`
- `GET /ready`
- `POST /auth/login` (MVP)
- `POST /auth/register` (MVP)

## Tests
- Run tests:
  - `make test`
- Formatting and lint:
  - `make fmt`
  - `make lint`
- Adding tests:
  - place tests under `tests/` using pytest

## Debugging/Logging
- Set `LOG_LEVEL=DEBUG` (in `.env`) to increase verbosity.
- Each response includes `X-Request-ID`; logs include `request_id=...` for correlation.
- Request timing is logged with `latency_ms` in request completion logs.
- Tool calls/results are stored in `chat_messages` (`tool_name`, `tool_args`, `tool_result`).

---

## Docs
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/PROMPTS.md`
