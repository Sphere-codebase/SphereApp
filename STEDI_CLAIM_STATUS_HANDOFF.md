# Stedi Claim Status Handoff

## 1. Executive Summary

The Stedi Claim Status minimum production-safe path has been implemented as a gated, configuration-driven payer status refresh flow. It adds the backend configuration, schema, models, migration, Stedi client, Stedi request mapper, API route, admin UI controls, and focused tests needed to refresh and store the latest payer claim status without persisting raw Stedi payloads, raw X12, Authorization headers, or API keys.

No real Stedi requests were run for this handoff. The integration only calls Stedi when `STEDI_ENABLED=true` and `STEDI_API_KEY` is configured.

## 2. What Was Implemented

- Stedi runtime configuration for enablement, API key, base URL, timeout, and optional billing provider fallbacks.
- A dependency-injected Stedi Claim Status client using `httpx` with timeout, network error handling, HTTP error handling, trace ID extraction, and normalized status mapping.
- A Stedi claim status payload mapper that builds the minimum base request from claim, payer, clinic billing provider, patient, and patient policy data.
- Data validation for missing payer Stedi trading partner ID, member ID, patient first name, patient last name, patient DOB, service date, and billing provider organization plus NPI or tax ID.
- Latest normalized Stedi status fields on `claims`.
- Clinic-scoped `claim_status_checks` history rows for success, no-match, disabled, configuration error, validation error, and Stedi error outcomes.
- Admin-maintained Stedi payer ID on insurance companies.
- Platform admin-maintained clinic billing provider profile fields.
- Admin claims list/detail exposure of latest Stedi status and submitted timestamp.
- Admin UI `Update status` action that calls `POST /api/claims/{claim_id}/refresh-status` and updates table/detail state.
- Patient create flow support for DOB and insurance group number so required Stedi matching data can be captured earlier.
- API documentation entry for the claim status refresh endpoint.

## 3. Files Changed

### Config

- `.env.example`
- `app/core/config.py`
- `app/api/deps.py`

### Models/Migrations

- `app/db/migrations/versions/0030_stedi_claim_status.py`
- `app/db/models/__init__.py`
- `app/db/models/claim.py`
- `app/db/models/claim_status_check.py`
- `app/db/models/clinic.py`
- `app/db/models/insurance_company.py`
- `app/db/models/patient_insurance_policy.py`

### Stedi Service/Client/Mapper

- `app/services/stedi/__init__.py`
- `app/services/stedi/client.py`
- `app/services/stedi/claim_status.py`

### API Routes/Schemas

- `app/api/routes/claims.py`
- `app/api/routes/admin_claims.py`
- `app/api/routes/admin_insurance_companies.py`
- `app/api/routes/platform_admin.py`
- `app/api/routes/patients.py`
- `app/api/routes/agent.py`
- `app/schemas/claims.py`
- `app/schemas/admin_dashboard.py`
- `app/schemas/admin_catalogs.py`
- `app/schemas/platform_admin.py`
- `app/schemas/patients.py`
- `app/repositories/patients.py`
- `app/services/patients.py`

### Frontend Admin UI

- `frontend-dev/src/features/admin/pages/AdminPage.tsx`
- `frontend-dev/src/features/admin/api/client.ts`
- `frontend-dev/src/features/admin/api/schemas.ts`
- `frontend-dev/src/api/platformAdmin.ts`
- `frontend-dev/src/types/platformAdmin.ts`
- `frontend-dev/src/components/admin/organisms/Clinics.tsx`

### Tests

- `tests/test_stedi_claim_status.py`
- `tests/test_new_patient_api.py`
- `frontend-dev/src/__tests__/admin.test.tsx`

### Docs

- `docs/API.md`
- `docs/STEDI_CLAIM_STATUS_PLAN.md`
- `docs/STEDI_DATA_GAP_REPORT.md`
- `docs/STEDI_INTEGRATION.md`
- `STEDI_CLAIM_STATUS_HANDOFF.md`

## 4. Exact Data Now Required for a Successful Refresh

- `STEDI_API_KEY`: configured in the runtime environment only; never committed or logged.
- `STEDI_ENABLED`: must be `true`.
- `insurance_companies.stedi_trading_partner_service_id`: payer routing ID, stored as a string so leading zeros are preserved.
- Clinic billing provider NPI or tax ID: `clinics.billing_provider_npi` or `clinics.billing_provider_tax_id`; environment fallbacks exist for local smoke testing.
- Clinic billing provider organization name: `clinics.billing_provider_organization_name`; environment fallback exists for local smoke testing.
- Patient first name, last name, DOB, and gender: first name, last name, and DOB are hard validation inputs; gender is sent only when it maps to `M` or `F`.
- Patient insurance `member_id`: matching `patient_insurance_policies.member_id` for the claim patient and payer.
- Optional `group_number`: captured on `patient_insurance_policies.group_number`; not currently sent in the minimum Stedi base payload.
- Claim service date: `claims.service_date`, or min/max line dates from `claim_procedure_facts.service_date`.
- Claim billed amount: `claims.billed_amount_total`; sent as `encounter.submittedAmount` when present.
- Optional `submitted_at`: captured on `claims.submitted_at`; currently returned as a warning if missing and not included in the Stedi payload.

## 5. Known Limitations

- Patient-as-subscriber only.
- No dependent support.
- No ETIN.
- No 837 claim submission.
- No 277CA storage.
- No 835/ERA storage.
- Claim status history is stored in `claim_status_checks`, but there is no dedicated history UI yet.
- Full test/lint blocked by missing local dependencies.

## 6. Verification Results Exactly as Observed

- `docker compose config` passed.
- `python3 -m compileall app tests` passed.
- `git diff --check` passed.
- `make test` failed because `.venv/bin/pytest` does not exist.
- `make lint` failed because `.venv/bin/ruff` does not exist.
- Focused pytest could not run because `sqlalchemy` is not installed.
- Frontend focused test could not run because `vitest`/`node_modules` is missing.

## 7. Client Acceptance Checklist

- Confirm production environment has `STEDI_ENABLED=true` and `STEDI_API_KEY` set through secret management.
- Confirm no Stedi API key or Authorization header is present in logs, audit entries, API responses, committed files, or status history rows.
- Run migration `0030_stedi_claim_status` in the target environment.
- Populate each payer's `insurance_companies.stedi_trading_partner_service_id`.
- Populate each clinic billing provider profile with organization name and either NPI or tax ID.
- Confirm claim patients have first name, last name, DOB, gender when available, and payer member ID.
- Confirm claims intended for refresh have service date and billed amount.
- Confirm admin users can see and edit payer Stedi IDs.
- Confirm platform admin users can see and edit clinic billing provider fields.
- Confirm admin users can click `Update status` on a test-safe claim and see latest status fields update.
- Confirm `claim_status_checks` stores only summaries and safe error metadata.

## 8. Suggested Next Milestone

- Prepare environment and run full tests.
- Add dependent/subscriber support.
- Add ETIN support if required by payers.
- Add claim status history UI.
- Add 837 submission.
- Add 277CA/835 lifecycle.
