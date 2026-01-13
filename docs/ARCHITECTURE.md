# ARCHITECTURE.md

## Overview
This service is a backend for a doctor-facing claims assistant. It supports:
- Authenticated, multi-tenant access
- A `/chat` endpoint that uses an LLM (LM Studio) with tool calling
- Database-backed storage of patients, claims, payments
- Full audit trail of chat sessions, messages, and tool calls/results

### High-level flow
1) Doctor uses Web UI to send a message (optionally tied to a claim).
2) Backend authenticates request and resolves `current_user` + `tenant_id`.
3) Backend builds a prompt (system + developer policy + short history + claim context).
4) Backend calls LLM (LM Studio OpenAI-compatible endpoint) with `tools` schemas.
5) If LLM requests a tool, backend:
   - validates args (Pydantic)
   - enforces tenant isolation
   - executes tool handler (DB or service)
   - stores tool call + result to DB
6) Backend returns assistant answer (and optional UI actions such as form schema).

---

## Layers and responsibilities

### `app/api/`
FastAPI routers and request/response wiring.
- No business logic beyond validating inputs and calling services.
- Auth dependency injection lives here (via `Depends`).

### `app/services/`
Orchestration and business logic.
- `chat_orchestrator.py`: tool-loop, prompt assembly, persistence of messages.
- `claim_scoring.py`: placeholder for integration with a scoring model/tool later.

### `app/llm/`
LLM client + tool registry.
- `client.py`: OpenAI-compatible HTTP calls to LM Studio.
- `tools/registry.py`: tool definitions + mapping to handlers.
- Tools are **backend-executed** functions. LLM only requests them.

### `app/db/`
Database connection and models.
- `session.py`: engine/session creation.
- `models/`: SQLAlchemy ORM models.
- Alembic migrations under `app/db/migrations/`.

### `app/core/`
Cross-cutting concerns.
- `config.py`: settings via env
- `security.py`: JWT auth helpers
- `logging.py`: log format and request IDs

---

## Multi-tenancy and security model
- Every patient/claim/payment row belongs to a `tenant_id`.
- Tools must accept a `RequestContext` containing `tenant_id` and `user_id`.
- All DB queries must filter by `tenant_id` (and user restrictions where required).
- Never accept `tenant_id` from client to authorize a request.

---

## Storage of chat sessions
We store:
- `chat_sessions`: per conversation (doctor + optional claim reference)
- `chat_messages`: each message including:
  - role: user/assistant/tool
  - content: text
  - tool_name/tool_args/tool_result (when applicable)
  - timestamps

This provides traceability and supports audits/debugging.

---

## Failure modes
- LM Studio unavailable → return 503 with consistent error body.
- Unknown tool call → refuse and proceed safely (no backend execution).
- Cross-tenant access attempt → return 404 (do not reveal existence).

---

## Notes
This document is intentionally short (1–2 pages). Update as the code evolves.
