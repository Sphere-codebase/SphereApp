# Stedi Claim Status Integration

## Environment

- `STEDI_ENABLED`: defaults to `false`. Set to `true` to allow claim status refresh calls.
- `STEDI_API_KEY`: Stedi API key. Do not commit or log this value.
- `STEDI_BASE_URL`: defaults to `https://healthcare.us.stedi.com/2024-04-01`.
- `STEDI_TIMEOUT_SECONDS`: defaults to `60`.
- `STEDI_PROVIDER_NPI`: optional fallback BillingProvider NPI when the clinic row does not have one.
- `STEDI_PROVIDER_TAX_ID`: optional fallback BillingProvider TIN when the clinic row does not have one.
- `STEDI_PROVIDER_ORGANIZATION_NAME`: optional fallback BillingProvider organization name when the clinic row does not have one.

The integration posts JSON to:

```text
POST {STEDI_BASE_URL}/change/medicalnetwork/claimstatus/v2
```

Stedi's official docs recommend starting with the base claim status request and note that exactly one BillingProvider is required in `providers`: https://www.stedi.com/docs/healthcare/check-claim-status and https://www.stedi.com/docs/api-reference/healthcare/post-healthcare-claim-status.

## Data Requirements

- Payer: `insurance_companies.stedi_trading_partner_service_id`.
- Subscriber: matching `patient_insurance_policies.member_id` for claim patient and payer.
- Optional subscriber group number: `patient_insurance_policies.group_number`.
- Patient: first name, last name, date of birth. Gender is sent only when it maps to `M` or `F`.
- Service dates: `claims.service_date`, or min/max `claim_procedure_facts.service_date`.
- Billing provider: clinic billing provider organization name plus NPI or TIN. Env fallbacks are used only when clinic fields are empty.

## Request Flow

1. User clicks `Update status` from the admin claim table or claim detail dialog.
2. Frontend calls `POST /api/claims/{claim_id}/refresh-status`.
3. Backend enforces the existing claim scope and update permission.
4. Backend validates required Stedi fields and returns safe field-level errors if data is missing.
5. Backend calls Stedi with an `httpx` timeout when enabled and configured.
6. Backend stores the latest normalized status on `claims`.
7. Backend stores a row in `claim_status_checks` with redacted request/response summaries only.
8. Backend writes an audit event without Authorization headers or raw PHI payloads.

## Missing Data Modal

When `POST /api/claims/{claim_id}/refresh-status` returns
`STEDI_MISSING_REQUIRED_DATA`, the admin dashboard opens a guided modal titled
`Missing Stedi data`. The modal only shows sections named by
`error.details.missing[*].field`:

- `insurance_company.stedi_trading_partner_service_id`: fills the payer Stedi ID used for payer matching. IDs are stored as strings so leading zeros are preserved.
- `patient_insurance_policy.member_id`: fills the member ID that should match the patient's insurance card. `group_number` can be added at the same time, but is optional.
- `clinic.billing_provider`: fills the billing provider organization name plus either NPI or Tax ID.

The modal uses claim-scoped `GET /api/claims/{claim_id}/stedi-data` and
`PATCH /api/claims/{claim_id}/stedi-data` endpoints. These endpoints reuse the
same claim update permission and clinic scoping as the status refresh action.
Audit records store changed field names only and do not include member IDs, raw
Stedi payloads, or `STEDI_API_KEY`.

## Limitations

- This integration only refreshes payer claim status. It does not submit claims.
- The patient is treated as the subscriber for this milestone.
- Dependent/subscriber-not-patient support is not implemented yet.
- ETIN is not required for claim status refresh.
- 837 claim submission, 277CA acknowledgements, and 835/ERA processing are not included in this milestone.
- Real Stedi claim status checks are intended for production claims that have reached payer processing.
- Zero returned claims are stored as `NO_MATCH`; this does not necessarily mean the claim is invalid.
- Raw Stedi request/response PHI and raw X12 are not persisted.
- Payer-specific matching can require more identifiers; this implementation starts with the recommended base payload.

## Smoke Test

1. Apply the migration.
2. Populate `insurance_companies.stedi_trading_partner_service_id`.
3. Populate clinic billing provider fields or configure `STEDI_PROVIDER_*` fallbacks.
4. Confirm the claim has patient name, DOB, payer member ID, and service date.
5. Set `STEDI_ENABLED=true`, `STEDI_API_KEY`, and optional `STEDI_BASE_URL`.
6. Open the admin dashboard, find the claim, and click `Update status`.
7. Confirm the table/detail show latest payer status and last checked time.
8. Confirm `claim_status_checks` contains only summaries and no API key.
