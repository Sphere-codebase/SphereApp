# Refactor Audit

## Current folder map (app/*)

```
app/
  api/
    deps.py
    routes/
      admin.py
      admin_claims.py
      admin_diagnosis_codes.py
      admin_insurance_companies.py
      admin_mcp_codes.py
      admin_patients.py
      policy_links.py
      auth.py
      chat.py
      chat_sessions.py
      claims.py
      health.py
      patients.py
  core/
    config.py
    logging.py
    security.py
  db/
    id_utils.py
    session.py
    migrations/
    models/
  llm/
    client.py
    tools/
      registry.py
      schemas.py
  middleware/
    request_id.py
    request_logging.py
  parsers/
    pdf/
      aetna_eob.py
      interface.py
      pdf_parse.py
    policy/
      aetna_policy.py
  repositories/
    claims.py
    codes.py
    coverage.py
    patients.py
    users.py
  schemas/
    admin_catalogs.py
    admin_dashboard.py
    admin_users.py
    auth.py
    chat.py
    chat_sessions.py
    claims.py
    patients.py
  services/
    chat_orchestrator.py
    claim_scoring.py
    claims/
      ingestion.py
    policy/
      rules_refresh.py
  utils/
    time.py
  main.py
```

## Routers/endpoints and service usage

- app/api/routes/auth.py
  - POST /auth/login, POST /auth/register, POST /auth/dev-token, GET /auth/me
  - Services: none (DB/session/auth helpers only)
- app/api/routes/admin.py
  - GET /api/admin/users, GET /api/admin/users/{user_id}, POST /api/admin/users, POST /api/admin/users/{user_id}/reset-password
  - Services: none (DB/session/auth helpers only)
- app/api/routes/admin_claims.py
  - GET /api/admin/claims, GET /api/admin/claims/{claim_id}
  - Services: none
- app/api/routes/admin_diagnosis_codes.py
  - GET/POST/GET/DELETE /api/admin/diagnosis-codes
  - Services: none
- app/api/routes/admin_insurance_companies.py
  - GET/POST/GET/DELETE /api/admin/insurance-companies
  - Services: none
- app/api/routes/admin_mcp_codes.py
  - GET/POST/GET/DELETE /api/admin/mcp-codes
  - Services: none
- app/api/routes/admin_patients.py
  - GET /api/admin/patients
  - Services: none
- app/api/routes/policy_links.py
  - GET/POST/PATCH/DELETE /api/admin/policy-links
  - POST /api/admin/policy-links/{policy_link_id}/parse
  - GET /api/admin/policy-links/{policy_link_id}/rules
  - Services: app.services.policy.rules_refresh.parse_policy_link_and_store
- app/api/routes/claims.py
  - GET/POST/PATCH/GET /api/claims
  - POST /api/claims/{claim_id}/mcp-codes
  - GET /api/claims/{claim_id}/policy-links
  - POST /api/claims/ingest-pdf
  - POST /api/claims/ingest-pdf-local (admin only)
  - Services: app.services.claims.ingestion.ingest_pdf_from_upload, app.services.claims.ingestion.ingest_pdf_from_path
- app/api/routes/chat.py
  - POST /chat
  - Services: app.services.chat_orchestrator.ChatOrchestrator
- app/api/routes/chat_sessions.py
  - GET/GET/POST/DELETE/GET /api/chat/sessions
  - Services: none
- app/api/routes/health.py
  - GET /health, GET /, GET /ready, GET /api/status
  - Services: none
- app/api/routes/patients.py
  - GET/POST/GET /api/patients
  - Services: none

## Canonical flow for PDF ingestion

- Entry points:
  - POST /api/claims/ingest-pdf (upload)
  - POST /api/claims/ingest-pdf-local (admin-only debug)
- Flow (current):
  1) app/api/routes/claims.py delegates to app/services/claims/ingestion.py
  2) app/parsers/pdf/interface.py parse_pdf_document(Path) returns {"pdf": parsed, "error_message": ...}
  3) app/services/claims/ingestion.py normalizes payload and orchestrates repository writes
  4) Inserts/updates tables:
     - patients, insurance_companies, claims
     - diagnosis_codes, claim_diagnosis_codes
     - mcp_codes, claim_mcp_codes
     - claim_procedure_facts, claim_procedure_diagnosis
     - claim_line_coverage
     - chat_sessions, chat_messages
  5) Idempotency today: reuse claim if same doctor/patient/insurer/service_date/total_billed and line count match; link tables use ON CONFLICT DO NOTHING; claim_line_coverage uses ON CONFLICT DO UPDATE keyed by claim_id+mcp_code.

## Canonical flow for policy link parsing

- Entry points:
  - POST /api/admin/policy-links/{policy_link_id}/parse
  - LLM tool: app/llm/tools/registry.py -> parse_policy_link_and_store
- Flow (current):
  1) app/services/policy/rules_refresh.parse_policy_link_and_store loads PolicyLink and InsuranceCompany
  2) app/parsers/policy/aetna_policy.parse_policy(url, payer_code)
     - local mode: dlc_modul parser modules imported if installed
     - http mode: POST to parser service
  3) Parsed policy stored as PolicyRule row

## Duplicated/conflicting modules and risks

- Ingestion orchestration now lives in app/services/claims/ingestion.py with repository helpers for DB writes.
- PDF parsing is centralized in app/parsers/pdf/interface.py; routes do not perform parsing logic directly.
- Dynamic module loading by file path has been removed in favor of static parser modules.
- Naming is mixed between CPT and MCP in the PDF ingestion flow, which increases confusion and risks incorrect usage.

## Naming inconsistencies and proposed conventions

- Mixed usage: "cpt" in parsed payloads/logs vs "mcp" in models/routes.
- Proposed convention: use MCP in code-level identifiers (variables, function names, DTOs), keep DB column names unchanged.
- Keep parser payload fields as-is when reading (e.g., "cpt" key) but normalize to MCP in internal structures.

## Refactor plan

Phase 1 (safe moves/renames, no behavior change)
- Create target structure under app/services/claims/, app/repositories/, app/parsers/pdf/, app/parsers/policy/, app/schemas/, app/utils/.
- Move modules to match their domain; update imports everywhere; keep route paths intact.
- Add __init__.py as needed.

Phase 2 (boundary cleanup, still no behavior change)
- Introduce canonical parse entry point: app/parsers/pdf/interface.py -> parse_pdf_document(path: Path) -> dict.
- Create canonical ingestion orchestration in app/services/claims/ingestion.py:
  - ingest_pdf_from_upload
  - ingest_pdf_from_path (debug/local)
  - ingest_parsed_payload
- Move all DB writes into repositories with clear upsert/link functions.
- Ensure idempotency for link tables and claim_line_coverage using conflict-safe upserts without explicit PK inserts for identity columns.
- Add INFO logs around each ingestion step and make them request_id aware.

Phase 3 (minimal tests + docs)
- Add an idempotency smoke test calling service-level ingestion twice for the same PDF and checking for duplicates in key tables.
- Update this audit doc with "After" notes.
