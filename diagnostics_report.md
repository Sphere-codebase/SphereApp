# Project Stack Summary
- FastAPI version: `fastapi==0.115.6` (pyproject.toml:10).\n- Python version: `>=3.11,<3.12` (pyproject.toml:6); README also states Python 3.11 (README.md:5-7).\n- DB type: Postgres via `postgresql+psycopg://` (app/core/config.py:49-52; README.md:83-85).\n- ORM: SQLAlchemy (sync) with `create_engine` (app/db/session.py:14-20).\n- Driver: psycopg v3 (`psycopg[binary]==3.2.3`, pyproject.toml:25). Also `psycopg2-binary` is present in requirements.txt but URL uses psycopg (app/core/config.py:49-52).\n- ASGI server: Uvicorn (pyproject.toml:11; README.md:105-108; Makefile `run` target). Reload mode is used in dev (`--reload` in README.md:105-108; Makefile: run target).

# Runtime Configuration Snapshot
- DATABASE_URL is set via settings with default (app/core/config.py:49-52).\n- Engine creation (sync) uses `create_engine(url, pool_pre_ping=True, future=True)` (app/db/session.py:14-16).\n- Pooling parameters: only `pool_pre_ping=True` is explicitly set; no `pool_size`, `max_overflow`, `pool_recycle`, or `statement_cache_size` configured (app/db/session.py:14-16).\n- NullPool is used only in Alembic migrations (app/db/migrations/env.py:35-46).

**Code excerpts (<=40 lines):**
```py
# app/core/config.py:49-52
    database_url: str = Field(
        "postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant",
        alias="DATABASE_URL",
    )
```

```py
# app/db/session.py:14-20
    url = database_url or settings.database_url
    return create_engine(url, pool_pre_ping=True, future=True)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
```

```py
# app/db/migrations/env.py:35-46
connectable = engine_from_config(
    section,
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)
```

# Request Lifecycle & Dependency Graph (Most Important)
- DB sessions are created via `get_db()` yielding a `SessionLocal()` and closed in `finally` (app/db/session.py:43-48).\n- `get_current_user` depends on `get_db`, performs DB queries in a threadpool and applies RLS context (app/core/security.py:65-123).\n- RLS context is also applied on SQLAlchemy Session `after_begin` event (app/db/session.py:23-40) and `apply_rls_context()` (app/core/tenancy.py:86-102). This implies per-request DB config can be set both during authentication and at session begin.

**Call graph (short):**
- `GET /auth/me`\n  - app/api/routes/auth.py:148-162 -> `get_current_user` (app/core/security.py:65-123)\n  - DB queries: `select(User)` and `select(Clinic.is_blocked)` (app/core/security.py:84-91)\n  - RLS: `apply_rls_context()` (app/core/security.py:117-123)

- `GET /ready`\n  - app/api/routes/health.py:79-128 -> `check_db()` uses `db.execute(text("SELECT 1"))` (app/api/routes/health.py:63-68)\n  - Optional LLM health check: `llm_client.health_check()` (app/api/routes/health.py:71-76; 105-111)

- `GET /api/chat/sessions`\n  - app/api/routes/chat_sessions.py:30-48 -> `policy.chat_scope_filters` + SQL `select(ChatSession)` (app/api/routes/chat_sessions.py:38-44)\n  - Dependencies: `get_db` + `get_current_user` (app/api/routes/chat_sessions.py:25-27)

- `GET /api/chat/sessions/{id}/messages`\n  - app/api/routes/chat_sessions.py:208-236 -> `select(ChatSession)` then `select(ChatMessage)` (app/api/routes/chat_sessions.py:214-234)\n  - Dependencies: `get_db` + `get_current_user` (app/api/routes/chat_sessions.py:25-27)

# Endpoint Hotspots (Code Pointers)
- **GET /auth/me**\n  - Router: `app/api/routes/auth.py` -> `me()` (lines 148-162).\n  - Dependencies: `get_current_user` (app/core/security.py:65-123).\n  - DB queries: `select(User)` + `select(Clinic.is_blocked)` (app/core/security.py:84-91).\n  - External calls: none (JWT decode + DB only).

- **GET /ready**\n  - Router: `app/api/routes/health.py` -> `ready()` (lines 79-128).\n  - Dependencies: `get_db`, `get_llm_client` (app/api/routes/health.py:26-34).\n  - DB query: `SELECT 1` (app/api/routes/health.py:63-68).\n  - External calls: optional LLM health check (app/api/routes/health.py:71-76, 105-111).

- **GET /api/chat/sessions**\n  - Router: `app/api/routes/chat_sessions.py` -> `list_sessions()` (lines 30-48).\n  - Dependencies: `get_db`, `get_current_user` (app/api/routes/chat_sessions.py:25-27).\n  - DB query: `select(ChatSession)` filtered by policy scope (app/api/routes/chat_sessions.py:38-44).\n  - External calls: none.

- **GET /api/chat/sessions/{id}/messages**\n  - Router: `app/api/routes/chat_sessions.py` -> `list_messages()` (lines 208-236).\n  - Dependencies: `get_db`, `get_current_user` (app/api/routes/chat_sessions.py:25-27).\n  - DB queries: `select(ChatSession)` then `select(ChatMessage)` (app/api/routes/chat_sessions.py:214-234).\n  - External calls: none.

# Database & Network Clues
- Default DATABASE_URL points to localhost:5432 (`postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant`). This indicates local Postgres (app/core/config.py:49-52; README.md:83-85).\n- README suggests Postgres runs via Docker Compose locally (README.md:69-78).\n- No `sslmode` parameters are present in the URL (app/core/config.py:49-52).\n- No explicit pgbouncer references found in repo (no config or URL hints).\n- Pooling: using SQLAlchemy default queue pool (no `NullPool` except Alembic). No explicit `pool_size`/`max_overflow` tuning (app/db/session.py:14-16).

# Existing Performance Logging Review
- Request timing middleware logging exists: `RequestLoggingMiddleware` logs JSON with duration, user_id, clinic_id, etc. (app/middleware/request_logging.py:14-43).\n- Performance logging middleware + SQL slow query logging: `app/core/performance_logging.py` includes thresholds `SLOW_REQUEST_MS = 1000`, `SLOW_QUERY_MS = 200` and logs to `logs/performance.log` (app/core/performance_logging.py:17-75).\n- The performance middleware is registered in FastAPI app (app/main.py:86-98).\n- SQL slow query logging uses `before_cursor_execute` / `after_cursor_execute` (app/core/performance_logging.py:178-215).\n- Connection pool event logging (connect/checkout/checkin) was added (app/core/performance_logging.py:133-176). This is additive and safe and enables correlation with request_id.

# OPTIONAL: Add Minimal Safe Instrumentation (only if missing)
- **Added** SQLAlchemy engine event listeners for `connect`, `checkout`, `checkin`, and a `do_connect` wrapper to measure connection creation duration. Logged with request_id.\n- **Location:** `app/core/performance_logging.py` (lines 133-176).\n- **Diff-style summary:**
  - Added `_current_request_id()` helper and appended request_id to performance logs.\n  - Added `do_connect` to time new DBAPI connections.\n  - Added `connect`, `checkout`, `checkin` listeners to log pool activity.

# Summary: The 5 Most Likely Causes (Ranked)
1) **Slow DB network/connection setup (new connections)**\n   - Evidence: new `connect` logs now available; default pool size not tuned (app/db/session.py:14-16). If frequent `CONNECT` logs appear, pool churn may be high.\n   - Validation: check `performance.log` for frequent `db connect` events or large connect durations; run load to see connect rate.

2) **Repeated RLS/tenant setup per request**\n   - Evidence: RLS context set in `apply_rls_context` (app/core/security.py:117-123) and also in Session `after_begin` (app/db/session.py:23-40).\n   - Validation: correlate slow requests with multiple `SET LOCAL` statements or check if multiple transactions are created per request.

3) **Blocking auth dependency (get_current_user)**\n   - Evidence: `get_current_user` runs DB queries in threadpool for every authenticated request (app/core/security.py:83-94).\n   - Validation: measure time spent in this dependency; check if `select(Clinic.is_blocked)` adds extra latency.

4) **Remote DB or Docker network latency**\n   - Evidence: README indicates local Docker Postgres (README.md:69-78), but production might use remote DB; no sslmode configured (app/core/config.py:49-52).\n   - Validation: compare latency between local and prod; inspect actual runtime DATABASE_URL and RTT.

5) **N+1 or large result sets in chat endpoints**\n   - Evidence: chat list and messages are simple queries, but no pagination on messages (list all messages) (app/api/routes/chat_sessions.py:208-236).\n   - Validation: check message count per session; measure query durations in `performance.log` for `slow sql` entries.

# Next Actions
1. Tail `logs/performance.log` and capture per-endpoint durations and `db connect` frequency during slow tabs.\n2. Confirm actual runtime `DATABASE_URL` and whether it is remote or behind a proxy; check for SSL or pgbouncer.\n3. For a single request, log or trace how many DB queries occur in `get_current_user` and downstream handlers.\n4. If `CONNECT` is frequent, increase pool size / reduce churn or investigate connection leaks.\n5. If `/api/chat/sessions/{id}/messages` is slow, add pagination or limit (after confirming data volume).
