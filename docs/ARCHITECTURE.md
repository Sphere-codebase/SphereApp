# Architecture

## Overview
SphereApp is a FastAPI backend for a clinic-scoped claims workflow. The current codebase supports:
- JWT auth for staff and clinic users
- clinic tenancy with DB-level context and route-level filtering
- claim and patient CRUD
- chat sessions plus an LLM tool loop
- policy-link/rule management and clinic/doctor overrides
- audit logging
- clinic and platform admin surfaces

## Main Runtime Pieces
- `app/main.py`
  - Creates the FastAPI app
  - Registers middleware, exception handlers, and routers
- `app/api/routes/`
  - HTTP entrypoints grouped by surface: auth, claims, patients, chat, admin, clinic, platform, agent
- `app/services/`
  - Business logic for chat orchestration, audit logging, claims ingestion, claim summaries, requirements
- `app/llm/`
  - LM Studio/OpenAI-compatible client plus the tool registry used by `/chat`
- `app/db/`
  - SQLAlchemy models, session management, migrations, and tenancy hooks
- `app/parsers/`
  - Policy parsing and remote PDF parsing helpers
- `pdf-parser-service/`
  - Separate parser service used by remote PDF ingestion

## Request Flow
1. Middleware assigns `X-Request-ID`, request logging, CORS, and performance logging.
2. Protected routes resolve `current_user` from the JWT.
3. Auth sets tenancy context for the SQLAlchemy session.
4. Route handlers enforce RBAC and fetch or mutate data.
5. Writes emit audit log entries through `AuditLogger`.

## Chat / LLM Flow
1. `POST /chat` resolves or creates a chat session.
2. The backend stores the user message.
3. Prompt assembly currently includes:
   - `docs/system_rules.md`
   - `docs/developer_policy.md`
   - up to the last 10 persisted `user`/`assistant` messages
4. The model may call registered tools.
5. Tool results are persisted as chat messages and fed back into the loop.
6. If a tool returns `action_required`, the response stops and the client must call `/api/chat/confirm-action`.

Important: claim context is not pre-expanded into the initial prompt. The model fetches claim, patient, policy, and code context through tools.

## Tenancy and DB Isolation
- Clinic is the tenant boundary.
- The session layer sets:
  - `row_security=on`
  - `app.current_clinic_id`
  - `app.is_platform_admin`
- In test mode the app also switches to the `app_rls` DB role to exercise RLS policies.
- Route handlers still apply explicit scope filters, especially for patients, claims, chat, and audit.

## Security Model
- JWT auth for users.
- `X-Admin-Token` only for `/auth/admin/users` bootstrap.
- `X-Agent-Token` for `/api/agent/*`.
- Blocked clinics are denied at auth time unless the user is `platform_staff_admin`.

## Persistence Model
- Core clinic-scoped data: clinics, users, patients, claims, chat sessions/messages, audit logs.
- Global reference data: insurance companies, MCP codes, diagnosis codes, policy links, policy rules.
- Override data: clinic and doctor policy overrides.
- Generated PDFs are stored on disk under `var/pdfs` with metadata in `claim_pdfs`.

## Caching
- `/auth/me`, admin reference lists, and chat session APIs use small in-process TTL caches.
- Cache invalidation exists for writes that affect those payloads.

## Planned / Not Yet Implemented
- No payer submission workflow.
- No async job queue for policy parsing or PDF generation.
- No separate domain service layer for every route surface; many handlers still perform direct query orchestration.
