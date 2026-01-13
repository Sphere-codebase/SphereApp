# Project Report

## 1) Metadata
- Generated at (local): Tue Jan 13 15:59:15 +04 2026
- Python (python --version): command not available (`python` not found). Use `.venv/bin/python --version`.
- Python (venv): `Python 3.11.14`
- Python (system python3): `Python 3.13.0`
- pip (venv): `pip 25.3 from /Users/user/Developer/pythonProject/SphereApp/.venv/lib/python3.11/site-packages/pip (python 3.11)`
- ruff: `ruff 0.8.4`
- mypy: `mypy 1.13.0 (compiled: yes)`
- pytest: `pytest 8.3.4`
- alembic: `alembic 1.14.0`
- OS/arch: `Darwin users-MacBook-Pro.local 24.0.0 Darwin Kernel Version 24.0.0: Tue Sep 24 23:36:30 PDT 2024; root:xnu-11215.1.12~1/RELEASE_X86_64 x86_64`

## 2) Project Summary (8–12 lines)
1) Реализован FastAPI backend с JWT auth (`/auth/login`, `/auth/dev-token`, `/auth/me`).
2) `/chat` обрабатывает сообщения с tool-loop и ограничением `LLM_MAX_STEPS`.
3) Есть tenant isolation на чтение/запись (все запросы фильтруются по `tenant_id`).
4) Сохраняется история чата: user/assistant сообщения, tool calls и tool results.
5) Реализованы read tools и write tools с подтверждением через `confirm=true`.
6) Write операции логируют ClaimEvent с user_id и chat_session_id.
7) Health endpoints: `/health` (liveness) и `/ready` (DB + опционально LLM).
8) Error responses стандартизованы и включают `X-Request-ID`.
9) Включено логирование request_id и latency, а также session_id/tool_steps в dev/test.
10) TODO: сервис claim_scoring остаётся заглушкой (`app/services/claim_scoring.py`).
11) Внешние зависимости: Postgres (через docker-compose) и LM Studio (OpenAI-compatible).
12) LLM readiness check включается через `READY_CHECK_LLM=true`.

## 3) Repository Structure (3 levels, filtered)
- app/
  - api/
    - routes/
      - auth.py
      - chat.py
      - health.py
  - core/
    - config.py
    - logging.py
    - security.py
  - db/
    - migrations/
      - env.py
      - versions/
    - models/
      - base.py
      - chat.py
      - claim.py
      - claim_event.py
      - patient.py
      - payment.py
      - tenant.py
      - user.py
    - session.py
  - llm/
    - client.py
    - tools/
      - registry.py
      - schemas.py
  - middleware/
    - request_id.py
    - request_logging.py
  - schemas/
    - auth.py
    - chat.py
  - services/
    - chat_orchestrator.py
    - claim_scoring.py
- docs/
  - API_CONTRACT.md
  - ARCHITECTURE.md
  - PROMPTS.md
  - developer_policy.md
  - system_rules.md
- tests/
  - TEST_PLAN.md
  - conftest.py
  - test_auth.py
  - test_chat_confirmations.py
  - test_chat_cross_tenant_read.py
  - test_chat_invalid_tool_args.py
  - test_chat_max_steps.py
  - test_chat_no_tools.py
  - test_chat_one_tool.py
  - test_chat_unknown_tool.py
  - test_db_migrations.py
  - test_health.py
  - test_llm_tools.py
  - test_llm_unavailable.py
  - test_request_id.py
- alembic.ini
- docker-compose.yml
- Makefile
- pyproject.toml
- README.md

## 4) API Endpoints
- `POST /auth/login`: email+password → access_token (JWT)
- `POST /auth/dev-token`: dev/test only; user_id → access_token
- `GET /auth/me`: current user profile (JWT required)
- `POST /chat`: LLM chat with tool-loop (JWT required). See `docs/API_CONTRACT.md`.
- `GET /health`: liveness probe (always 200)
- `GET /ready`: readiness probe (DB; optionally LLM with `READY_CHECK_LLM=true`)

/chat request/response:
- Request: `message` (required), `session_id` (optional), `claim_id` (optional), `metadata` (optional)
- Response: `session_id`, `assistant_message`, `ui_actions`, `action_required`, `proposed_changes`, `debug` (dev/test only)
- Full contract and examples: `docs/API_CONTRACT.md`

## 5) Configuration (ENV)
All variables are read via `app/core/config.py`:
- `ENV` (default `dev`): runtime mode (`dev`, `test`, `prod`)
- `LOG_LEVEL` (default `INFO`)
- `CORS_ORIGINS` (default empty list): comma-separated or JSON array
- `LMSTUDIO_BASE_URL` (default `http://localhost:1234/v1`)
- `LLM_MODEL` (default `local-model`)
- `LLM_TIMEOUT_SECONDS` (default `60`)
- `LLM_MAX_STEPS` (default `5`)
- `LLM_TEMPERATURE` (default `0.2`)
- `DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant`)
- `JWT_SECRET` (default `change-me`) **required in prod**
- `JWT_ALGORITHM` (default `HS256`)
- `JWT_EXPIRES_MINUTES` (default `60`)
- `MAX_USER_MESSAGE_CHARS` (default `4000`)
- `MAX_CONTEXT_CHARS` (default `8000`)
- `READY_CHECK_LLM` (default `false`)

Dev/test/prod: determined by `ENV` (`dev`, `test`, `prod`).

## 6) Tools / Registry
Tools defined in `app/llm/tools/registry.py`:
- `search_patients`: read-only, search by name
- `get_patient`: read-only, fetch by id
- `get_claim`: read-only, fetch by id
- `list_claims`: read-only, list by patient_id
- `request_form`: read-only, returns UI form schema
- `create_claim_draft`: write, requires `confirm=true`
- `update_claim_fields`: write, requires `confirm=true`

Unknown tool calls:
- Not executed; result is `{ "error": { "code": "UNKNOWN_TOOL" } }`.

Max tool steps:
- Controlled by `LLM_MAX_STEPS`.

## 7) DB and Migrations
Tables:
- `tenants`, `users`, `patients`, `claims`, `payments`, `chat_sessions`, `chat_messages`, `claim_events`

Indexes/constraints:
- `tenant_id` indexes on all multi-tenant tables
- Foreign keys between tenants/users/patients/claims/payments/chat_sessions/chat_messages/claim_events

Migration commands:
- `alembic revision --autogenerate -m "describe change"`
- `alembic upgrade head`
- `alembic downgrade -1`

Tenant isolation:
- All DB queries include `tenant_id` filters (read and write).
- Cross-tenant access returns 404 for safety.

## 8) Logging & Observability
- `X-Request-ID` is accepted from client; otherwise a UUIDv4 is generated.
- Every response includes `X-Request-ID`.
- Logs include `request_id=...`, request path, status, and `latency_ms`.
- In dev/test, `/chat` logs `chat_session_id` and `tool_steps`.
- LLM 503 reproduction: stop LM Studio or point `LMSTUDIO_BASE_URL` to a dead endpoint.
  - `/chat` returns `LLM_UNAVAILABLE` when the LLM client fails.
  - `/ready` returns 503 when `READY_CHECK_LLM=true` and LLM is unavailable.

## 9) Tests & Quality
Command outputs (real):
```
$ make fmt
.venv/bin/ruff format .
54 files left unchanged
.venv/bin/ruff check . --fix
All checks passed!

$ make lint
.venv/bin/ruff check .
All checks passed!

$ make type
.venv/bin/mypy app
Success: no issues found in 40 source files

$ make test
.venv/bin/pytest -q
/Users/user/Developer/pythonProject/SphereApp/.venv/lib/python3.11/site-packages/pytest_asyncio/plugin.py:208: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
ssssssssssss.ss.........                                                 [100%]
=============================== warnings summary ===============================
.venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854
  /Users/user/Developer/pythonProject/SphereApp/.venv/lib/python3.11/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Test map:
- `tests/test_chat_no_tools.py`: no tools path
- `tests/test_chat_one_tool.py`: one tool call then answer
- `tests/test_chat_unknown_tool.py`: unknown tool handling
- `tests/test_chat_invalid_tool_args.py`: invalid tool args handled safely
- `tests/test_chat_max_steps.py`: max tool steps reached behavior
- `tests/test_chat_cross_tenant_read.py`: cross-tenant read 404
- `tests/test_chat_confirmations.py`: write confirmation gate and ClaimEvent
- `tests/test_llm_unavailable.py`: LLMUnavailable → 503 format
- `tests/test_request_id.py`: request_id header + 422/500 formatting
- `tests/test_auth.py`: auth flow (401/200)
- `tests/test_health.py`: /health and /ready
- `tests/test_db_migrations.py`: migrations + CRUD (skips if Postgres not running)

Skips/xfails:
- `s` in test output indicates DB-backed tests skipped because Postgres isn’t reachable.
  Start Postgres (`docker compose up -d`) to run them.

## 10) Run Commands (copy-paste)
Local run:
```
make venv
make install
docker compose up -d
make run
```

Minimal curl examples:
```
# dev token (dev/test only)
curl -X POST http://localhost:8000/auth/dev-token \\
  -H "Content-Type: application/json" \\
  -d '{"user_id":"<user-uuid>"}'

# login
curl -X POST http://localhost:8000/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"doctor@example.com","password":"secret"}'

# chat
curl -X POST http://localhost:8000/chat \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Summarize claim","claim_id":"<claim-uuid>"}'

# health/ready
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

If LM Studio is not running:
- `/chat` returns 503 with `LLM_UNAVAILABLE`.
- `/ready` returns 503 only when `READY_CHECK_LLM=true`.
- Start LM Studio and ensure `LMSTUDIO_BASE_URL` is correct.

## Changed Files (git status --porcelain)
```
 M .gitignore
 M AGENT_INSTRUCTIONS.md
 M Makefile
 M README.md
 M app/api/__init__.py
 M app/api/routes/__init__.py
 M app/api/routes/auth.py
 M app/api/routes/chat.py
 M app/api/routes/health.py
 M app/core/config.py
 M app/core/logging.py
 M app/core/security.py
 M app/db/__init__.py
 M app/db/migrations/README.md
 M app/db/models/__init__.py
 M app/db/models/chat.py
 M app/db/models/claim.py
 M app/db/models/patient.py
 M app/db/models/payment.py
 M app/db/models/tenant.py
 M app/db/models/user.py
 M app/db/session.py
 M app/llm/__init__.py
 M app/llm/client.py
 M app/llm/tools/__init__.py
 M app/llm/tools/registry.py
 M app/llm/tools/schemas.py
 M app/main.py
 M app/schemas/auth.py
 M app/schemas/chat.py
 M app/services/chat_orchestrator.py
 M docs/API_CONTRACT.md
 M docs/ARCHITECTURE.md
 M pyproject.toml
?? .env.example
?? alembic.ini
?? app/db/migrations/env.py
?? app/db/migrations/versions/
?? app/db/models/base.py
?? app/db/models/claim_event.py
?? app/middleware/
?? docker-compose.yml
?? tests/conftest.py
?? tests/test_auth.py
?? tests/test_chat_confirmations.py
?? tests/test_chat_cross_tenant_read.py
?? tests/test_chat_invalid_tool_args.py
?? tests/test_chat_max_steps.py
?? tests/test_chat_no_tools.py
?? tests/test_chat_one_tool.py
?? tests/test_chat_unknown_tool.py
?? tests/test_db_migrations.py
?? tests/test_health.py
?? tests/test_llm_tools.py
?? tests/test_llm_unavailable.py
?? tests/test_request_id.py
```
