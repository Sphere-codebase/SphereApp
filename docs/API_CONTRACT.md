# API_CONTRACT.md

This doc defines the contract for the `/chat` endpoint and core error behaviors.
All responses are JSON.

## Authentication
All `/chat` requests require an `Authorization: Bearer <JWT>` header (MVP).


## Request/Response Headers
### X-Request-ID (correlation id)
- Client MAY send `X-Request-ID: <string>` to correlate logs and retries.
- If missing, server MUST generate a UUIDv4 request id.
- Server MUST echo the final request id back in **every** response (success and error) as `X-Request-ID`.

Notes:
- `X-Request-ID` is used for troubleshooting and log correlation.
- It does not change authorization/tenant resolution.


## POST /chat
### Request body
```json
{
  "message": "Please analyze claim 123 and tell me missing docs",
  "session_id": "optional-existing-session-id",
  "claim_id": "optional-claim-id-for-context",
  "metadata": {
    "client_message_id": "optional",
    "ui_locale": "en-US"
  }
}
```

### Response body (success)
```json
{
  "session_id": "sess_abc123",
  "assistant_message": "Here is what I found...",
  "action_required": false,
  "proposed_changes": null,
  "ui_actions": [
    {
      "type": "form",
      "id": "missing_fields",
      "title": "Please provide missing information",
      "schema": {
        "fields": [
          {
            "name": "date_of_service",
            "label": "Date of Service",
            "type": "date",
            "required": true
          }
        ]
      }
    }
  ],
  "debug": {
    "tool_steps": 2
  }
}
```

### Response notes
- `ui_actions` is optional and may be empty.
- `action_required`/`proposed_changes` are returned when a write requires explicit confirmation.
- Write tools require `confirm=true`; without confirmation, the response will include `action_required=true`.
- `debug` is optional and MUST be disabled in production mode.

---

## GET /health
- Always returns 200 when process is running.

## GET /ready
- Returns 200 when DB is reachable.
- If `READY_CHECK_LLM=true`, returns 503 when LLM is unavailable.

---

## Error model (standard)
All errors use:
```json
{
  "error": {
    "code": "string",
    "message": "human readable",
    "details": { "any": "json" }
  }
}
```
All error responses include the `X-Request-ID` header.

### 401 Unauthorized
- Missing/invalid JWT.

### 404 Not Found
- Resource not found OR cross-tenant access attempt (do not leak existence).

### 422 Validation error
- Invalid request payload.

### 503 Service Unavailable (LLM)
When LM Studio is down/unreachable/timeouts, return:
```json
{
  "error": {
    "code": "LLM_UNAVAILABLE",
    "message": "LLM service is unavailable",
    "details": {
      "error": "LLM request failed",
      "base_url": "http://localhost:1234/v1",
      "timeout_seconds": 60
    }
  }
}
```

### 500 Internal Server Error
- Unexpected errors. Do not leak stack traces in production.

---

## Idempotency / retries
- Client may retry `/chat` requests on 503.
- Optional `metadata.client_message_id` can be used to deduplicate if implemented.

---

## Examples
### Minimal request
```json
{ "message": "List recent claims for patient John Smith" }
```

### Continue session
```json
{ "session_id": "sess_abc123", "message": "Now open the last claim" }
```
