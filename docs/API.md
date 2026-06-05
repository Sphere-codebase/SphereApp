# API Reference

## Common
- Protected endpoints require `Authorization: Bearer <JWT>`.
- All responses include `X-Request-ID`.
- Error responses use the app-wide wrapper:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

## System
- `GET /` -> `{ "service": "SphereApp API", "status": "ok" }`
- `GET /health` -> `{ "status": "ok" }`
- `GET /ready` -> `{ ok, checks, details }`
  - `checks.db` is required for HTTP 200.
  - `checks.llm` is `warn` when `READY_CHECK_LLM=false`.
- `GET /api/status` -> deep readiness snapshot:
  - `db_ready`, `llm_ready`, `overall_ready`, `reason`
  - `checked_at`, `env`, `llm_model`, `lmstudio_base_url`, `llm_max_steps`

## Auth
- `POST /auth/login`
  - Request: `{ "email", "password" }`
  - Response: `{ "access_token", "token_type": "bearer" }`
- `GET /auth/me`
  - Response: `{ id, email, full_name, role, roles, clinic_id, clinic_name, is_active }`
- `POST /auth/dev-token`
  - Dev/test only.
  - Request: `{ "user_id" }`
- `POST /auth/admin/users`
  - Bootstrap endpoint protected by `X-Admin-Token`, not JWT.
  - Creates a user and returns a bearer token for that user.

## Chat
- `POST /chat`
  - Request: `{ "message", "session_id"?, "metadata"? }`
  - Response: `{ session_id, assistant_message, ui_actions, debug?, action_required, proposed_changes? }`
  - If `session_id` is omitted, the backend creates a session automatically.
- `POST /api/chat/confirm-action`
  - Request: `{ session_id, proposal_id?, decision, tool, arguments, payload? }`
  - Supported `tool` values are currently:
    - `create_claim_draft`
    - `update_claim_fields`
  - Response: `{ "status": "confirmed" | "rejected", "result" }`

## Chat Sessions
- `GET /api/chat/sessions`
  - Query: `limit` default `50`, `offset` default `0`
  - Response: bare list of `{ id, doctor_id, created_at, claim_id?, patient_id?, title? }`
- `POST /api/chat/sessions`
  - Request: `{ "title"?, "claim_id"? }`
  - Response: one `ChatSessionResponse`
- `GET /api/chat/sessions/{session_id}`
- `PATCH /api/chat/sessions/{session_id}`
  - Request: `{ "title"?, "claim_id"? }`
- `DELETE /api/chat/sessions/{session_id}`
  - Deletes the session, its chat messages, and audit rows tied to that chat session entity.
- `GET /api/chat/sessions/{session_id}/messages`
  - Returns only persisted `user` and `assistant` messages, ordered ascending.

## Patients
- `GET /api/patients`
  - Query: `query?`, `limit=25`, `offset=0`
  - Response: bare list of patient list items, not a paginated wrapper object.
- `POST /api/patients`
  - Accepts either:
    - `NewPatientCreateRequest` with `patient_name`, phones, address, insurances
    - `PatientCreateRequest` with `first_name`, `last_name`, `date_of_birth`
- `GET /api/patients/{patient_id}`
- `PATCH /api/patients/{patient_id}`
  - Request: partial `{ first_name?, last_name?, date_of_birth? }`
- `GET /api/patients/{patient_id}/claims`
  - Query: `limit=20`, `offset=0`
  - Response: `{ items, limit, offset, total }`

## Claims
- `GET /api/claims`
  - Query: `patient_id?`, `insurance_company_id?`, `status?`
  - Response: bare list of `ClaimResponse`
- `GET /api/claims/my`
  - Query: `limit=20`, `offset=0`, `q?`, `date_from?`, `date_to?`
  - Always scoped to the current doctor, even if the user has a higher clinic/platform role.
  - Response: `{ items, limit, offset, total }`
- `GET /api/claims/my-summary`
  - Same filters and scope as `/api/claims/my`
- `POST /api/claims`
  - Requires `insurance_company_id` plus either `patient_id` or inline `patient`
  - Optional `session_id` attaches the created claim to an existing chat session
- `GET /api/claims/{claim_id}`
  - Response: `{ id, claim_status, updated_at, patient, insurance_company_id, service_date, mcp_codes, diagnosis_codes }`
- `POST /api/claims/{claim_id}/requirements`
- `POST /api/claims/{claim_id}/refresh-status`
  - Refreshes the latest payer status through Stedi when enabled/configured.
  - Response: `{ claim_id, status, status_code, status_category, message, amount_paid, checked_at, payer_claim_number }`
- `PATCH /api/claims/{claim_id}`
- `POST /api/claims/{claim_id}/mcp-codes`
  - Request: `{ "code"?, "mcp_codes": [] }`
  - Returns a bare list of `{ claim_id, mcp_code }`
- `DELETE /api/claims/{claim_id}/mcp-codes/{code}`
- `POST /api/claims/{claim_id}/diagnosis-codes`
  - Request: `{ "code"?, "diagnosis_codes": [] }`
  - Returns a bare list of `{ claim_id, diagnosis_code }`
- `DELETE /api/claims/{claim_id}/diagnosis-codes/{code}`
- `POST /api/claims/{claim_id}/finalize`
  - Sets `claim_status` to `FINAL` and returns claim detail
- `POST /api/claims/{claim_id}/pdf`
  - Response: `{ "pdf_id", "pdf_url" }`
- `GET /api/claims/{claim_id}/policy-links`
  - Returns one item per claim MCP code:
    - `mcp_code`
    - `policy_url`
    - `missing_policy_link`
- `GET /api/claims/{claim_id}/financial`
- `POST /api/claims/{claim_id}/financial/refresh`
  - Financial responses use `{ claim_id, currency, predicted_total_paid_amount, predicted_per_mcp, flags, updated_at }`
- `POST /api/claims/ingest-pdf`
  - Multipart form-data:
    - `file`
    - `session_id?`
- `POST /api/claims/ingest-pdf-local`
  - Platform staff admin only.
  - Debug/local ingestion endpoint.
- `DELETE /api/claims/{claim_id}`

## Lookups
- `GET /api/codes/mcp?query=...`
- `GET /api/codes/diagnosis?query=...`
  - Both return up to 20 results.
- `GET /api/insurance-companies`
  - Query: `q?`, `limit=20`, `offset=0`
  - Response: `{ items, limit, offset, total }`

## Insurance Rules
- `GET /api/insurance-rules/policy-links`
  - Query: `insurance_company_id?`, `mcp_code?`
  - Response: `{ items }`
- `GET /api/insurance-rules/{policy_link_id}/rules`
  - Returns latest extracted rule payload:
    - `{ policy_link_id, extracted_at, rules_json }`
  - If no rule exists yet, returns the same shape with `null` fields.
- `GET|PUT|DELETE /api/insurance-rules/{policy_link_id}/clinic-override`
- `GET|PUT|DELETE /api/insurance-rules/{policy_link_id}/doctor-override`

## Clinic Admin
- `GET /api/clinic/dashboard`
  - Query aliases: `from?`, `to?`
- `GET /api/clinic/doctors`
- `PATCH /api/clinic/doctors/{doctor_id}`
- `GET /api/clinic/audit-logs`
  - Query: `actor_id?`, `action?`, `entity?`, `date_from?`, `date_to?`, `limit=25`, `offset=0`
  - Response: bare list, not `{ items, total }`
- `GET /api/clinic/audit-logs/export`
  - Query: `include_diff=0|1`

## Platform Admin
- `GET|POST /api/platform/clinics`
- `PATCH /api/platform/clinics/{clinic_id}`
- `GET /api/platform/audit`
  - Query aliases: `from?`, `to?`
  - Response: `{ items, limit, offset, total }`
- `GET /api/platform/audit/export`
- `GET /api/platform/usage`
  - Query: `date_from?`, `date_to?`, `clinic_id?`

## Platform Directory / Reference Admin
- `GET|POST /api/admin/users`
- `GET|PATCH /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/reset-password`
- `GET /api/admin/patients`
- `GET /api/admin/claims`
- `GET /api/admin/claims/{claim_id}`
- `GET /api/admin/audit-logs`
- `GET|POST /api/admin/insurance-companies`
- `GET|PATCH|DELETE /api/admin/insurance-companies/{company_id}`
- `GET|POST /api/admin/mcp-codes`
- `GET|PATCH|DELETE /api/admin/mcp-codes/{code}`
- `GET|POST /api/admin/diagnosis-codes`
- `GET|PATCH|DELETE /api/admin/diagnosis-codes/{code}`
- `GET|POST /api/admin/policy-links`
- `PATCH|DELETE /api/admin/policy-links/{policy_link_id}`
- `POST /api/admin/policy-links/{policy_link_id}/parse`
  - Request: `{ "confirm": false | true }`
- `GET /api/admin/policy-links/{policy_link_id}/rules`

## AI History
- `GET /api/ai-history`
  - Query: `actor_id?`, `action?`, `claim_id?`, `date_from?`, `date_to?`, `limit=25`, `offset=0`
  - Response: `{ items, limit, offset, total }`

## Files
- `GET /api/files/pdfs/{filename}`
  - Streams a generated claim PDF after claim-level RBAC checks.

## Agent API
- All `/api/agent/*` endpoints require `X-Agent-Token`.
- Implemented endpoints:
  - `GET /api/agent/claim-context`
  - `PATCH /api/agent/claims/{claim_id}`
  - MCP / diagnosis add-remove endpoints
  - `GET /api/agent/policy-links`
  - `GET /api/agent/policy-rules/{policy_link_id}/latest`
  - `POST /api/agent/claims/{claim_id}/requirements`
  - `POST /api/agent/claims/{claim_id}/validate`
