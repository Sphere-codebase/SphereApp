# CLIENT_VALUE_REPORT.md

## Executive summary

SphereApp is a FastAPI backend, with a React frontend present under `frontend-dev/`, for clinic-scoped medical claims preparation and administration. The product supports authenticated users, clinic tenancy, patient and claim workflows, chat sessions, LLM tool-calling, policy-link/rule management, PDF claim ingestion, generated claim PDFs, audit logging, and clinic/platform administration. The backend is built around SQLAlchemy models, Alembic migrations, explicit RBAC policy helpers, request correlation middleware, and readiness/status endpoints. The LLM integration is implemented against an OpenAI-compatible local/remote provider, documented as LM Studio, with tools for claims, patients, policy links, virtual claims, and guarded write confirmations. The database model is substantial: it includes users, clinics, patients, claims, codes, policy links/rules, overrides, audit logs, claim PDFs, claim facts, ML-ready tables, and virtual claim checklist state. The work is billable because it represents production-grade backend application development, not just UI scaffolding or prototypes: there are route surfaces, persistence, migrations, authorization, tests, diagnostics, and operational controls. Full test/lint verification was not completed in this audit because the expected `.venv` executables are missing, but Docker Compose configuration validation passed and the repository contains extensive feature tests.

## Project identification

Docs reviewed:

- Present: `README.md`, `docs/API.md`, `docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/PROMPTS_AND_LLM.md`, `tests/TEST_PLAN.md`, `app/db/migrations/README.md`, `diagnostics_report.md`
- Missing at repository root: `PROJECT.md`, `SPEC.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `OPERATIONS.md`, `THREAT_MODEL.md`, `API.md`, `SMOKE_TESTS.md`

Product summary in 6 sentences:

SphereApp is a multi-tenant claims assistant for clinics and doctors. It provides authenticated access to patient records, claim records, code lookups, payer policy links, claim summaries, dashboards, and administrative catalogs. It uses chat sessions and an LLM tool loop to help users collect claim facts, inspect policy data, maintain virtual claim checklists, and propose guarded claim writes that require confirmation. It persists operational data in Postgres via SQLAlchemy and Alembic migrations, including clinic isolation metadata and row-level security policy migrations. It includes PDF ingestion and generated claim PDF support, plus a separate parser-service implementation for remote PDF parsing. It also provides audit logging, request IDs, readiness checks, structured error responses, and platform/clinic admin surfaces for operational oversight.

## What was implemented

Main Python packages/modules:

- `app/api/routes/`: FastAPI route modules for auth, chat, claims, patients, admin, platform, clinic, files, health, agent, policy links, insurance rules, dashboards, AI history, and codes.
- `app/core/`: configuration, security, RBAC policy, tenancy/RLS helpers, response caching, structured logging, error handlers, and performance logging.
- `app/db/`: SQLAlchemy session creation, ID generation, models, and Alembic migrations.
- `app/services/`: chat orchestration, audit logging, user roles, patient logic, claims ingestion/PDF/requirements/summary/virtual-claim services, and policy rule refresh.
- `app/llm/`: OpenAI-compatible LLM client and tool registry/schemas.
- `app/parsers/`: policy parsing and remote PDF parser client.
- `app/pdf/`: claim PDF construction/rendering helpers.
- `app/repositories/`: persistence helpers for claims, patients, users, coverage, and codes.
- `app/schemas/`: Pydantic API schemas.
- `pdf-parser-service/`: standalone FastAPI PDF parser service.

FastAPI route groups found:

- System health/status: `/`, `/health`, `/ready`, `/api/status` in `app/api/routes/health.py`.
- Auth/session identity: `/auth/login`, `/auth/admin/users`, `/auth/dev-token`, `/auth/me` in `app/api/routes/auth.py`.
- Chat and virtual claim workflow: `/chat`, `/api/chat/confirm-action`, `/api/chat/sessions`, `/api/chat/sessions/{id}/messages`, `/api/chat/sessions/{id}/virtual-claim...` in `chat.py`, `chat_actions.py`, `chat_sessions.py`, and `chat_virtual_claims.py`.
- Patients and patient claims: `/api/patients...` in `patients.py`.
- Claims: `/api/claims`, `/api/claims/my`, `/api/claims/my-summary`, claim detail/update/finalize/PDF/policy-links/financial/ingest/delete in `claims.py`.
- Code lookups: `/api/codes/mcp`, `/api/codes/diagnosis` in `codes.py`.
- Insurance companies and insurance rules: `/api/insurance-companies`, `/api/insurance-rules...` in `insurance_companies.py` and `insurance_rules.py`.
- Clinic admin: `/api/clinic/dashboard`, doctors, audit logs, audit export in `clinic_admin.py`.
- Platform admin: `/api/platform/clinics`, platform audit/export, usage in `platform_admin.py`.
- Platform directory/reference admin: `/api/admin/users`, patients, claims, audit logs, insurance companies, MCP codes, diagnosis codes, policy links, policy parse/rules in admin route modules.
- Files: `/api/files/pdfs/{filename}` in `files.py`.
- Agent API: `/api/agent/*` in `agent.py`, guarded by `X-Agent-Token`.
- Policy parser API: `/api/policy/parse` in `app/parsers/policy/policy_parse.py`.

Database/migration/storage evidence:

- SQLAlchemy session and engine: `app/db/session.py`.
- Models: `app/db/models/*.py`, including `User`, `Clinic`, `Patient`, `Claim`, `ChatSession`, `ChatMessage`, `AuditLog`, `PolicyLink`, `PolicyRule`, policy overrides, claim PDFs, claim facts, ML prediction/training tables, and virtual claim tables.
- Migrations: `app/db/migrations/versions/0001_initial.py` through `0029_virtual_claim_checklists.py`.
- RLS/tenant hardening: `0027_tenant_hardening_rls.py`; virtual claim RLS: `0029_virtual_claim_checklists.py`.
- Performance indexes: `0028_perf_indexes.py`.
- Audit tables: `0022_audit_logs.py`.

Auth/session/CSRF/security evidence:

- JWT bearer auth and password hashing are implemented in `app/core/security.py`.
- Login, admin bootstrap, dev-token, and current-user endpoints are implemented in `app/api/routes/auth.py`.
- RBAC and tenancy filters are centralized in `app/core/policy.py`.
- Request-scoped clinic/RLS settings are applied in `app/core/security.py`, `app/core/tenancy.py`, and `app/db/session.py`.
- Agent endpoints are protected by `X-Agent-Token` in `app/api/deps.py`.
- Admin user bootstrap is protected by `X-Admin-Token` in `app/api/routes/auth.py`.
- Blocked-clinic denial is implemented in `app/core/security.py` and surfaced by `ClinicBlockedError`.
- CSRF protection was not found. This may be acceptable for bearer-token APIs, but it is not implemented evidence.

Provider check evidence:

- LLM provider health check calls `GET /models` through `LLMClient.health_check()` in `app/llm/client.py`.
- `/ready` optionally checks the LLM depending on `READY_CHECK_LLM`; `/api/status` exposes DB and LLM readiness in `app/api/routes/health.py`.
- The chat provider call is OpenAI-compatible `POST /chat/completions` in `app/llm/client.py`.
- Remote PDF parser integration is implemented in `app/parsers/pdf/remote_client.py` and calls `/v1/parse`.
- Standalone parser service health and parse endpoints exist in `pdf-parser-service/main.py`.

Scheduler evidence:

- No scheduler, cron worker, background job queue, periodic task runner, Celery/RQ/APScheduler integration, or `BackgroundTasks` implementation was found.
- Policy parsing and refresh are implemented as synchronous route/tool flows, especially `app/services/policy/rules_refresh.py` and `app/api/routes/policy_links.py`.

Alerting/incident/diagnostics evidence:

- Request IDs are implemented in `app/middleware/request_id.py` and returned in `X-Request-ID`.
- Request logging is implemented in `app/middleware/request_logging.py`.
- Structured error wrappers and LLM/DB unavailable handlers are implemented in `app/core/logging.py`.
- Performance logging and SQL timing hooks are implemented in `app/core/performance_logging.py`.
- Audit logging is implemented in `app/services/audit.py` and exposed via admin/clinic/platform audit routes.
- Health/readiness/status endpoints are implemented in `app/api/routes/health.py`.
- No external alert dispatch, incident ticketing, pager integration, or notification channel was found.

Verification commands run:

| Command | Result | Notes |
|---|---:|---|
| `git status --short` | Passed | Output was empty; working tree was clean before the report file was created. |
| `git log --oneline --decorate -n 30` | Passed | Recent history includes commits for LLM speed, route fixes, audit/platform admin, RLS/tenant isolation, observability, performance, and agent/tool layer. |
| `git tag --list` | Passed | No tags were listed. |
| `make test` | Failed before tests ran | `make: .venv/bin/pytest: No such file or directory`; likely cause is missing local virtualenv or dependencies. |
| `make lint` | Failed before lint ran | `make: .venv/bin/ruff: No such file or directory`; likely cause is missing local virtualenv or dependencies. |
| `docker compose config` | Passed | Compose rendered a Postgres 16 service with healthcheck, port `5432`, and `postgres_data` volume. |

## Evidence table

| Feature | Code evidence | Test evidence | Documentation evidence | Client value |
|---|---|---|---|---|
| FastAPI application shell and route registration | `app/main.py`, `app/api/routes/*.py` | `tests/test_route_registration.py`, `tests/test_health.py`, `tests/test_removed_ui_routes.py` | `README.md`, `docs/API.md`, `docs/ARCHITECTURE.md` | Establishes a real backend API surface rather than a mock. |
| Auth and current-user session identity | `app/core/security.py`, `app/api/routes/auth.py`, `app/schemas/auth.py` | `tests/test_auth.py`, `tests/test_register.py`, `tests/test_chat_sessions_api.py` | `docs/API.md`, `docs/ARCHITECTURE.md` | Enables controlled access and user-specific workflows. |
| RBAC and tenant isolation | `app/core/policy.py`, `app/core/tenancy.py`, `app/db/session.py`, migration `0027_tenant_hardening_rls.py` | `tests/test_rbac_claims.py`, `tests/test_rbac_my_claims.py`, `tests/test_rbac_admin_access.py`, `tests/test_clinic_isolation.py` | `docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md` | Protects clinic data boundaries and supports regulated multi-tenant use. |
| Blocked clinic handling | `app/core/security.py`, `app/core/exceptions.py`, migration `0026_clinics_is_blocked.py` | `tests/test_clinic_isolation.py` | `docs/ARCHITECTURE.md` | Lets platform admins suspend clinic access without deleting data. |
| Patient management | `app/api/routes/patients.py`, `app/repositories/patients.py`, patient/address/insurance models | `tests/test_new_patient_api.py`, `tests/test_clinic_isolation.py` | `docs/API.md`, `docs/DOMAIN_MODEL.md` | Supports intake and patient-linked claim preparation. |
| Claims CRUD and claim relations | `app/api/routes/claims.py`, `app/repositories/claims.py`, claim/code models | `tests/test_rbac_claims.py`, `tests/test_claim_relations_api.py`, `tests/test_my_claims_api.py` | `docs/API.md`, `docs/DOMAIN_MODEL.md` | Provides the core billable claim workflow. |
| My claims and claim summaries | `app/services/claims/summary.py`, `app/repositories/claims.py`, `app/api/routes/claims.py` | `tests/test_my_claims_api.py`, `tests/test_my_claims_summary_api.py` | `docs/API.md` | Gives doctors scoped work queues and financial/claim overview data. |
| Claim requirements engine | `app/services/claims/requirements.py`, `/api/claims/{id}/requirements` | `tests/test_llm_tools.py`, `tests/test_virtual_claims.py`, `tests/test_claim_policy_links_flow.py` | `docs/API.md`, `docs/PROMPTS_AND_LLM.md` | Converts policy and claim facts into missing-field guidance. |
| Virtual claim checklist workflow | `app/services/claims/virtual_claims.py`, `app/api/routes/chat_virtual_claims.py`, migration `0029_virtual_claim_checklists.py` | `tests/test_virtual_claims.py`, `tests/test_chat_confirmations.py`, `tests/test_llm_tools.py` | `docs/PROMPTS_AND_LLM.md`, `docs/ARCHITECTURE.md` | Reduces hallucination and makes claim-prep state deterministic. |
| Chat sessions and message history | `app/services/chat_orchestrator.py`, `app/api/routes/chat.py`, `chat_sessions.py` | `tests/test_chat_no_tools.py`, `test_chat_one_tool.py`, `test_chat_multiple_tools.py`, `test_chat_session_reuse.py`, `test_chat_session_messages_api.py` | `docs/API.md`, `docs/PROMPTS_AND_LLM.md`, `tests/TEST_PLAN.md` | Gives users conversational continuity with persisted context. |
| LLM tool registry | `app/llm/tools/registry.py`, `app/llm/tools/schemas.py` | `tests/test_llm_tools.py`, `tests/test_llm_tools_procedure_codes.py`, `tests/test_llm_tools_bot_capabilities.py` | `docs/PROMPTS_AND_LLM.md` | Turns the assistant into a scoped workflow actor with explicit tools. |
| Guarded AI write confirmations | `app/api/routes/chat_actions.py`, `app/llm/tools/registry.py` | `tests/test_chat_confirmations.py`, `tests/test_llm_tool_writes_rbac.py` | `docs/API.md`, `docs/PROMPTS_AND_LLM.md` | Prevents silent AI writes and creates auditable user-confirmed changes. |
| LLM provider integration/readiness | `app/llm/client.py`, `app/api/routes/health.py` | `tests/test_llm_unavailable.py`, `tests/test_status_api.py`, `tests/test_health.py` | `docs/PROMPTS_AND_LLM.md`, `docs/API.md`, `README.md` | Supports operational checks and graceful handling when the model is unavailable. |
| Policy links and rules | `app/api/routes/policy_links.py`, `app/api/routes/insurance_rules.py`, `app/services/policy/rules_refresh.py`, policy models | `tests/test_admin_policy_links_api.py`, `tests/test_admin_policy_rules_api.py`, `tests/test_policy_parser_service.py` | `docs/API.md`, `docs/DOMAIN_MODEL.md`, `README.md` | Gives admins payer-policy source control and extracted rule review. |
| Policy parser endpoint | `app/parsers/policy/policy_parse.py`, `app/parsers/policy/*.py` | `tests/parsers/policy/test_in_process_parser.py` | `docs/API.md`, `README.md` | Enables policy extraction from payer pages. |
| PDF ingestion | `app/services/claims/ingestion.py`, `app/parsers/pdf/remote_client.py`, `pdf-parser-service/main.py` | `tests/test_claims_pdf_ingest.py`, `tests/test_claim_ingest_idempotent.py`, `tests/test_remote_pdf_parser.py`, `tests/test_remote_pdf_parser_hardened.py` | `README.md`, `docs/ARCHITECTURE.md` | Converts PDF/EOB inputs into claim facts and coverage records. |
| Claim PDF generation/file serving | `app/services/claims/pdf.py`, `app/pdf/claim_pdf.py`, `app/api/routes/files.py` | `tests/test_claim_pdf.py` | `docs/API.md`, `README.md` | Produces downloadable claim documentation. |
| Admin reference/catalog management | `app/api/routes/admin*.py`, `policy_links.py` | `tests/test_admin_users_api.py`, `test_admin_diagnoses_api.py`, `test_admin_procedure_codes_api.py`, `test_admin_agencies_api.py`, `test_admin_dashboard_api.py` | `docs/API.md` | Lets platform staff maintain users, payers, codes, policies, and read-only operations. |
| Clinic admin | `app/api/routes/clinic_admin.py` | `tests/test_dashboard_api.py`, `tests/test_audit_logs.py`, `tests/test_clinic_isolation.py` | `docs/API.md`, `docs/ARCHITECTURE.md` | Gives clinic leadership doctor and audit visibility. |
| Platform admin | `app/api/routes/platform_admin.py` | `tests/test_rbac_admin_access.py`, `tests/test_admin_dashboard_api.py`, `tests/test_audit_logs.py` | `docs/API.md` | Supports multi-clinic operations and platform oversight. |
| Audit logging | `app/services/audit.py`, `app/db/models/audit_log.py`, migration `0022_audit_logs.py` | `tests/test_audit_logs.py` | `docs/API.md`, `docs/DOMAIN_MODEL.md`, `docs/ARCHITECTURE.md` | Provides compliance-grade traceability for writes and security events. |
| Request correlation and diagnostics | `app/middleware/request_id.py`, `app/middleware/request_logging.py`, `app/core/performance_logging.py`, `app/core/logging.py` | `tests/test_request_id.py`, `tests/test_chat_file_logs.py`, `tests/test_vercel_runtime.py` | `docs/API.md`, `diagnostics_report.md` | Helps support, debugging, latency analysis, and incident triage. |
| Docker Compose local DB | `docker-compose.yml` | `docker compose config` passed in this audit | `README.md` | Gives local/dev Postgres bootstrap and repeatable environment setup. |
| Scheduler/async job queue | Not found | Not found | `docs/ARCHITECTURE.md` explicitly says no async job queue | This is not implemented; future work may be billable. |
| External alerting/incident dispatch | Not found | Not found | Not found | Diagnostics exist, but alert delivery is not implemented. |

## Role-based assessment

Product Manager:

- Implemented value: The app covers a coherent MVP workflow: authenticate, manage patients, prepare claims, use chat assistance, validate claim readiness, inspect policy rules, and administer clinics/platform data.
- Caveat: Payer submission is not implemented; docs explicitly list no payer submission workflow.

CTO:

- Implemented value: The backend has real architecture depth: FastAPI, SQLAlchemy, Alembic, RBAC, tenant scoping, RLS migrations, LLM tool boundaries, structured errors, caching, and Dockerized Postgres config.
- Caveat: Full test/lint verification could not run until `.venv` is installed.

Backend Lead:

- Implemented value: Route modules, services, repositories, schemas, models, and migrations are separated enough to support continued development. Tests cover route behavior, RBAC, schema drift, chat tools, claims, and migrations.
- Caveat: `docs/ARCHITECTURE.md` notes that not every route has a separate domain service layer; some handlers still orchestrate queries directly.

Security Engineer:

- Implemented value: JWT auth, password hashing, admin/agent token gates, RBAC policy functions, clinic block controls, RLS migrations, audit logging, and request IDs are present.
- Caveat: CSRF was not found, no rate limiting was found, and README contains an admin-key-shaped example value that should be treated as sensitive unless confirmed fake.

DevOps:

- Implemented value: Docker Compose config validates, health/readiness endpoints exist, Vercel serverless entrypoint exists at `api/index.py`, runtime warnings exist for production misconfiguration, and performance logging is implemented.
- Caveat: Missing local `.venv` prevented `make test` and `make lint`; no scheduler/job worker deployment is present.

QA:

- Implemented value: The test suite is broad and maps to major features: auth, RBAC, clinic isolation, chat, tools, claims, policy links/rules, PDF parsing, audit logs, request IDs, schema drift, and dashboards.
- Caveat: In this audit, tests are test evidence by existence only, not verified pass evidence, because `make test` could not execute.

UX:

- Implemented value: The backend supports UX-facing workflows such as chat sessions, virtual claim panels, readiness state, dashboards, patients, claims, policy rules, and admin catalogs. Frontend code exists under `frontend-dev/`.
- Caveat: This audit focused on backend evidence and did not run frontend build/tests or perform browser verification.

Support/Ops:

- Implemented value: Request IDs, structured request logs, error wrappers, health/readiness/status endpoints, audit log exports, and performance logs support troubleshooting and client support.
- Caveat: There is no external alerting or incident notification integration.

Business Owner:

- Implemented value: The repo contains billable assets: production backend code, database schema, admin surfaces, AI-assisted workflow logic, policy parsing, PDF handling, tests, and deployment/local-run instructions.
- Caveat: Acceptance should be tied to running tests/builds in a prepared environment and demonstrating key workflows against a seeded database.

## Why this work is billable

- It implements core business workflows, not just documentation: auth, patients, claims, chat, virtual claim readiness, policy links/rules, PDF ingestion, audit logs, dashboards, and admin APIs all have code evidence.
- It includes database schema and migration work, which is a durable production asset and a major part of backend delivery.
- It includes security and multi-tenancy work: RBAC, route-level filters, RLS migrations, blocked-clinic behavior, admin/agent token boundaries, and tests.
- It includes AI workflow engineering: an LLM client, tool schema registry, guarded tool writes, persisted chat history, virtual claim state, confirmation flows, and LLM failure handling.
- It includes operational readiness: health/readiness/status endpoints, request IDs, structured error responses, audit logs, performance logging, Docker Compose config, and serverless entrypoint support.
- It includes a broad test corpus that demonstrates intended behavior across high-risk areas, even though the current local environment must be prepared before the suite can be verified.
- It provides reusable client value: faster claim preparation, clearer policy evidence, safer AI-assisted changes, better auditability, and a foundation for paid extensions such as payer submission or async processing.

## Risks and limitations

- `make test` and `make lint` did not run because `.venv/bin/pytest` and `.venv/bin/ruff` are missing.
- CSRF protection was not found. This may be acceptable for bearer JWT usage, but should be explicitly accepted or added depending on browser token storage choices.
- Rate limiting was not found.
- No scheduler, queue, or async job processor was found for policy parsing, PDF parsing, or long-running work.
- No payer submission workflow was found; `docs/ARCHITECTURE.md` also lists this as not implemented.
- No external alerting/incident dispatch was found.
- README contains an admin-token-shaped example value; do not reuse it and replace it with a placeholder if it is not intentionally fake.
- Several default development secrets exist in config/docs, such as default JWT/PDF parser values; production must override them.
- Frontend was not verified in this audit.
- LLM behavior depends on an external/local OpenAI-compatible provider; readiness can warn or fail depending on `READY_CHECK_LLM`.
- PDF parser tests include skip behavior for parser availability in some cases; full parser confidence requires running the prepared environment.

## Mismatches between docs and code

- Root docs requested by the audit are missing: `PROJECT.md`, `SPEC.md`, `REQUIREMENTS.md`, `ROADMAP.md`, root `ARCHITECTURE.md`, `OPERATIONS.md`, `THREAT_MODEL.md`, root `API.md`, and `SMOKE_TESTS.md`.
- `diagnostics_report.md` is stale: it says Python is `>=3.11,<3.12`, while `pyproject.toml` requires `~=3.12.0`; it also says DB pool settings are not configured, while current `app/db/session.py` uses `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, and `DB_POOL_PRE_PING`.
- README uses `LLM_BASE_URL` in the LM Studio section, but code settings use `LMSTUDIO_BASE_URL`.
- README policy parser integration mentions `PARSER_MODE` and `PARSER_BASE_URL`, but current settings expose `PDF_PARSER_URL` and `PDF_PARSER_API_KEY`; policy parsing is implemented through `app/parsers/policy/policy_parse.py` and `app/services/policy/rules_refresh.py`.
- README says the PDF parser lives under `app/parsers/pdf/` as `pdf_parse.py` plus `aetna_eob.py`; current `app/parsers/pdf/` contains `remote_client.py`, and the standalone parser implementation is under `pdf-parser-service/`.
- `docs/PROMPTS_AND_LLM.md` says `parse_policy_link_and_store` is registered but not accepted by chat confirmation. Current `app/api/routes/chat_actions.py` confirms `create_claim_draft`, `update_claim_fields`, and `propose_materialize_virtual_claim`, but still does not confirm `parse_policy_link_and_store`; the documented mismatch remains accurate.
- `docs/ARCHITECTURE.md` says generated PDFs are stored on disk under `var/pdfs`, while README says serverless file serving generates claim PDFs on demand for `/api/files/pdfs/{filename}`. Both may be true in different runtime paths, but this needs clarification in current docs.

## Suggested acceptance checklist for the client

- Prepare environment with Python 3.12 and run `make install`.
- Run `make test` and require a passing full backend test suite.
- Run `make lint` and require clean Ruff output.
- Run `docker compose config` and `make db-upgrade` against a known test database.
- Demonstrate `/health`, `/ready`, and `/api/status`.
- Demonstrate login and `/auth/me` with a seeded user.
- Demonstrate patient creation/list/detail with clinic scoping.
- Demonstrate claim create/update/finalize and `/api/claims/my`.
- Demonstrate chat session creation, message persistence, and an LLM unavailable 503 case.
- Demonstrate virtual claim checklist readiness and guarded materialization confirmation.
- Demonstrate policy-link creation, parse preview, confirmed parse/store, and rule retrieval.
- Demonstrate PDF ingestion and generated claim PDF access.
- Demonstrate audit logs for claim writes, AI confirmations, login, and blocked-clinic denial.
- Demonstrate cross-clinic denial/404 behavior for patients, claims, and chat sessions.
- Replace any sample token-looking values in docs with placeholders before client handoff.

## Suggested next paid milestone

Build an operational hardening and acceptance milestone:

- Set up the local/dev environment so `make test`, `make lint`, migrations, and frontend checks run reliably.
- Add or update missing root docs: `OPERATIONS.md`, `THREAT_MODEL.md`, `SMOKE_TESTS.md`, and a root `API.md` redirect or canonical link.
- Fix stale README/config mismatches for LM Studio and PDF/policy parser settings.
- Add rate limiting and document CSRF/token-storage posture.
- Add an async job queue or scheduler for PDF parsing and policy parsing, with status endpoints.
- Add external alerting hooks for readiness failures, parser failures, and slow-request thresholds.
- Produce a client demo script and seed data for acceptance testing.
