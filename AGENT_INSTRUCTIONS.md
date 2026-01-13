# AGENT_INSTRUCTIONS.md
> Purpose: This document is the **single source of truth** for how Codex must build the project from scratch.
> Keep it updated as you implement. Do not “re-invent” architecture—follow this plan.

## Project summary
Build a multi-tenant, authenticated **Doctor Claims Assistant** backend that:
- exposes a `/chat` endpoint for a web UI
- uses a local LLM (LM Studio OpenAI-compatible server) with **tool use**
- enforces **tenant & user isolation** in every DB operation
- stores **chat sessions + tool calls + tool results** for auditability
- supports “request form fields” when required data is missing

This repository is backend-only (FastAPI). A separate claim-scoring model/service will be integrated via a tool later.

---

## Key principles (non-negotiable)
1. **Backend is the authority**:
   - User identity comes only from JWT/session, not from LLM text.
2. **LLM never touches DB directly**:
   - LLM may only request tool calls; backend validates and executes.
3. **Tenant isolation everywhere**:
   - Every query includes `tenant_id` filter (and where relevant, `user_id`).
4. **Audit everything**:
   - Store messages, tool calls, tool args, tool results, timestamps.
5. **Write operations require confirmation**:
   - LLM can propose changes; backend must require explicit confirmation flag or separate confirm call.
6. **Fail gracefully**:
   - If LM Studio unavailable: return **503** with structured error body.
7. **Short sessions**:
   - Assume 1–3 messages, but architecture must still support longer sessions safely.

---

## Tech stack (locked)
- Python: **3.11**
- FastAPI + Uvicorn
- Pydantic v2
- SQLAlchemy 2.x + Alembic
- Postgres (local dev via Docker recommended)
- Auth: JWT (HS256) for MVP
- LLM client: httpx (OpenAI-compatible)
- Tests: pytest + httpx + pytest-asyncio
- Lint/format: ruff
- Typing: mypy (basic)

---

## Milestones and step-by-step plan
> Implement in order. Each milestone has **Definition of Done** (DoD).

### M0 — Repo bootstrap
**Tasks**
- Ensure folder structure matches the repository skeleton.
- Ensure all docs exist and are referenced from README.
- Confirm `make run`, `make test`, `make fmt` exist (even if tests are minimal at first).

**DoD**
- `python -m compileall app` passes.
- `ruff check .` runs (may pass with ignores until code exists).
- `pytest` runs (may have placeholder tests marked xfail).

---

### M1 — Configuration & logging
**Tasks**
- Mandatory: add request correlation id middleware:
  - read `X-Request-ID` from request headers (if present)
  - otherwise generate UUIDv4
  - set `X-Request-ID` header on every response (success + error)
  - include request_id in all logs
- Implement `app/core/config.py` using Pydantic Settings.
- Load env from `.env` (local dev) + real env in prod.
- Add structured logging helpers in `app/core/logging.py`.
- Configure CORS, app name, environment mode.

**DoD**
- Importing `app.core.config.settings` works.
- Startup logs show environment + LM base URL (without secrets).
- `.env.example` fully matches required variables.
- Request ID middleware is in place (read/generate UUIDv4, echo header, log request_id).
- Every response includes `X-Request-ID`.
- Logs include request_id and allow correlating failures.


---

### M2 — Database layer & migrations
**Tasks**
- Create SQLAlchemy engine/session (`app/db/session.py`).
- Define models for:
  - Tenant
  - User (doctor)
  - Patient
  - Claim
  - Payment
  - ChatSession
  - ChatMessage (incl. tool_call metadata)
- Add Alembic migrations folder, initial migration.
- Add basic CRUD helpers (read-only first).

**DoD**
- `alembic upgrade head` creates tables.
- Simple script or test can create tenant+user row and read it back.
- All tables include `tenant_id` where needed.

---

### M3 — Auth & request context
**Tasks**
- JWT auth: login endpoint (MVP) OR simple dev token creation.
- Middleware/dependency to resolve `current_user` and `tenant_id`.
- Add “request context” object passed to services/tools.

**DoD**
- Requests to protected endpoints fail without token (401).
- With token, `current_user.id` and `current_user.tenant_id` are available.
- No endpoint accepts `tenant_id` from client body for authorization decisions.

---

### M4 — LLM client (LM Studio) and tool registry
**Tasks**
- Implement `app/llm/client.py` for OpenAI-compatible chat completions:
  - base_url, model, timeout, retries
  - request includes `tools` schemas
  - parse tool calls from response
- Implement tool registry:
  - tool name → schema → handler function
  - Pydantic validation of tool args
- Start with read tools only:
  - `search_patients(query)`
  - `get_patient(patient_id)`
  - `get_claim(claim_id)`
  - `list_claims(patient_id)`
  - `request_form(fields)` (returns UI schema, does not write DB)

**DoD**
- Unit tests for tool arg validation.
- If LM Studio down: raises controlled error that maps to API 503.
- Tool registry refuses unknown tool names.

---

### M5 — Chat orchestrator (/chat endpoint)
**Tasks**
- Implement `app/services/chat_orchestrator.py`:
  - build system + developer prompts from docs files
  - include short conversation history + minimal claim/patient context
  - run tool loop with max steps (`LLM_MAX_STEPS`)
  - store all messages/tool calls in DB
- Implement API route `POST /chat`:
  - accepts message + optional `session_id` + optional `claim_id`
  - returns assistant text + optional UI actions (form schema) + session_id
- Enforce:
  - tenant isolation when loading claim/patient context
  - max tool steps (avoid infinite loops)

**DoD**
- Tests cover 3 scenarios:
  1) no tools, direct answer
  2) one tool call (e.g., get_claim) then answer
  3) unknown tool call -> orchestrator rejects and asks LLM to respond without it (or returns safe error)
- DB stores chat_session + chat_messages including tool metadata.

---

### M6 — Write tools with confirmations
**Tasks**
- Add draft/update tools:
  - `create_claim_draft(patient_id, fields...)`
  - `update_claim_fields(claim_id, patch...)`
- Require confirmation:
  - Either two-step API (propose → confirm)
  - Or include `confirm: true` flag validated on backend + UI confirmation gate
- Add audit events for write operations.

**DoD**
- Without confirmation: endpoint returns `action_required` with preview changes.
- With confirmation: updates are applied and logged in `claim_events` and chat log.

---

### M7 — Error handling & observability
**Tasks**
- Standardize error model (see docs/API_CONTRACT.md).
- Add `/health` and `/ready` endpoints:
  - `/ready` checks DB + optionally LLM connectivity (configurable).
- Add request IDs and correlate logs with chat_session_id.

**DoD**
- API errors are consistent JSON.
- 503 when LLM unavailable.
- 500 never leaks stack traces in production mode.

---

### M8 — Hardening & quality gates
**Tasks**
- Add ruff + mypy to CI (local Make targets are enough for MVP).
- Add test coverage for tenant isolation (attempt cross-tenant read -> 404).
- Add rate limits (optional) and size limits for inputs.

**DoD**
- `make fmt`, `make lint`, `make type`, `make test` all pass.
- Security tests for tenant isolation present.

---

## Implementation conventions
- Keep modules small and explicit.
- No “magic global state” besides settings.
- Prefer dependency injection via FastAPI `Depends`.
- Tools are pure functions that accept `(ctx, args)` and return JSON-serializable dict.

---

## Definition of Done (global)
Project is considered “MVP done” when:
- `/chat` works end-to-end with LM Studio tool use
- tenant/user isolation enforced and tested
- chat history stored (messages + tool calls/results)
- docs are updated and reflect reality
- Makefile targets work
