# Domain Model

## Tenant Boundary
- `clinic_id` is the active tenant key.
- Most operational records are clinic-bound directly.
- A small set of directories is global and shared across clinics.

## Core Entities
- `clinics`
  - Clinic record with optional address and `is_blocked`
- `users`
  - Authenticated actors
  - Current primary role is stored in `users.role`
  - Every user belongs to one clinic
- `patients`
  - Clinic-bound, doctor-owned patient records
  - Optional address and insurance policy/card data
- `claims`
  - Clinic-bound claim header linked to patient, doctor, and insurance company
- `chat_sessions`, `chat_messages`
  - Doctor-owned conversation history inside a clinic
- `audit_logs`
  - Unified audit trail keyed by clinic

## Claim-Related Tables
- `claims`
  - Header-level fields such as `claim_status`, `claim_number`, dates, and totals
- `claim_mcp_codes`
  - Many-to-many link between claims and MCP codes
- `claim_diagnosis_codes`
  - Many-to-many link between claims and diagnosis codes
- `claim_procedure_facts`
  - Procedure-level payment facts imported from PDFs / claim history
- `claim_line_coverage`
  - Coverage outcomes and rationale at the claim line level
- `claim_pdfs`
  - Generated PDF metadata for a claim
- `ml_predictions`, `mcp_payment_predictions`
  - Financial prediction inputs used by `/api/claims/{id}/financial`

## Patient-Related Tables
- `patients`
- `patient_insurance_policies`
- `insurance_cards`
- `addresses`

The API exposes only part of this structure today. Patient diagnosis assignment outside claims is not implemented.

## Policy / Rules Tables
- `insurance_companies`
  - Global payer directory
- `mcp_codes`
  - Global procedure code directory
- `diagnosis_codes`
  - Global diagnosis code directory
- `policy_links`
  - Global mapping of payer + MCP code -> source policy URL
- `policy_rules`
  - Latest extracted structured rule snapshots for a policy link
- `clinic_policy_overrides`
  - Clinic-scoped override JSON per policy link
- `doctor_policy_overrides`
  - Doctor-scoped override JSON per policy link

## Audit Model
- `audit_logs` stores:
  - `clinic_id`
  - actor identity and role snapshot
  - `action`, `entity`, `entity_id`
  - `diff_json`
  - `request_id`, `ip`, `user_agent`
  - optional `target_clinic_id`, `target_user_id`
  - `scope` (`clinic` or `platform`)

## Identifier Notes
- Most primary keys are `BIGINT`.
- The app generates IDs in code via `next_id(...)`; the docs should not assume auto-increment semantics.
- Request correlation uses string request IDs, returned as `X-Request-ID`.
