# Prompts and LLM

## Provider
- Current client: `app/llm/client.py`
- Protocol: OpenAI-compatible HTTP API
- Default base URL: `LMSTUDIO_BASE_URL=http://localhost:1234/v1`
- Readiness check hits `GET /models`
- Chat calls use `POST /chat/completions`

## Prompt Assembly
For `/chat`, the backend currently builds the prompt from:
1. `docs/system_rules.md`
2. `docs/developer_policy.md`
3. Up to the last 10 persisted `user` / `assistant` chat messages

There is no separate static “claim context” prompt section. Claim, patient, rule, and code context are fetched through tools during the loop, and the session virtual claim acts as the backend-owned claim-prep state.

## Chat Loop
- The model receives the registered tool schemas.
- Max tool steps are controlled by `LLM_MAX_STEPS` (default `5`).
- If the model returns no tool calls, the assistant text is returned directly.
- If a tool proposes a write, the API returns:
  - `action_required: true`
  - `proposed_changes`

## Registered Tools
- `search_patients`
- `get_patient`
- `get_claim`
- `list_claims`
- `get_virtual_claim`
- `request_form`
- `get_account`
- `time_now`
- `list_procedure_codes`
- `get_procedure_code`
- `list_policy_links_for_code`
- `get_policy_rules_for_link`
- `explain_coverage_for_code`
- `bootstrap_virtual_claim_context`
- `update_virtual_claim`
- `evaluate_claim_readiness`
- `list_missing_claim_fields`
- `get_virtual_claim_checklist`
- `update_virtual_claim_fields`
- `list_missing_virtual_claim_fields`
- `explain_virtual_claim_policy`
- `propose_materialize_virtual_claim`
- `get_bot_capabilities`
- `create_claim_draft`
- `update_claim_fields`
- `parse_policy_link_and_store`

## Confirmation Behavior
- `create_claim_draft` and `update_claim_fields` support the user-facing `/api/chat/confirm-action` flow.
- `parse_policy_link_and_store` exists in the tool registry, but the implemented chat confirmation endpoint does not accept it.
- Admin policy parsing is currently confirmed through `POST /api/admin/policy-links/{policy_link_id}/parse` with `{ "confirm": true }`.

## Tool Access Boundaries
- Tool execution uses the current user's `user_id`, `clinic_id`, and `role`.
- Data returned by tools is scoped through the same policy layer used by the HTTP API.
- Tool metadata for `get_bot_capabilities` is bilingual (`ru` and `en`).

## Persistence
- User messages, assistant messages, tool calls, and tool results are stored in `chat_messages`.
- `/api/chat/sessions/{id}/messages` intentionally returns only `user` and `assistant` rows, not `tool` rows.
- `/chat` responses may also include a structured `virtual_claim` object and a `virtual_claim_update` UI action so the frontend can render deterministic claim-prep state.

## Known Limits
- Only LM Studio/OpenAI-compatible backends are wired today.
- Prompt files fall back to hardcoded defaults if `docs/system_rules.md` or `docs/developer_policy.md` are missing.
- Legacy virtual-claim tool names remain registered for compatibility, but the preferred tool surface is `get_virtual_claim`, `update_virtual_claim`, `evaluate_claim_readiness`, and `list_missing_claim_fields`.
