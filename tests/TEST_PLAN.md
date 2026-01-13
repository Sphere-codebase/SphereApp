# TEST_PLAN.md

This document defines the minimum test coverage for the MVP.

## Test categories

### 1) Chat orchestrator tool-loop
Cover at least these scenarios:

1. **No tools**:
   - LLM returns plain assistant message.
   - Ensure response is returned and chat stored.

2. **One tool call then answer**:
   - LLM requests `get_claim`.
   - Backend executes tool and sends tool result back.
   - LLM returns final answer.
   - Assert tool call and tool result are persisted.

3. **Unknown tool call**:
   - LLM requests a tool not in registry.
   - Backend refuses to execute and returns safe behavior (either re-prompt or error).
   - Must not crash.

4. **Tool arg validation failure**:
   - LLM calls tool with invalid args.
   - Backend returns tool error result to LLM or terminates safely.

5. **Max steps reached**:
   - LLM keeps calling tools.
   - Backend stops at `LLM_MAX_STEPS` and returns safe message.

### 2) LLM unavailability → 503
- Mock LLM client to raise connect/timeout.
- `/chat` must return:
  - HTTP 503
  - error.code = `LLM_UNAVAILABLE`

### 3) Tenant isolation
- Create two tenants with patients/claims.
- With tenant A token, attempt to read tenant B claim:
  - Must return 404 (not 403) to avoid leaking existence.

### 4) Auth
- No token → 401
- Invalid token → 401
- Valid token → 200

### 5) Persistence
- Chat session created on first message.
- Subsequent message with session_id appends messages.
- Tool calls stored with tool_name, args, result.

## Suggested structure
- `tests/test_chat_no_tools.py`
- `tests/test_chat_one_tool.py`
- `tests/test_chat_unknown_tool.py`
- `tests/test_llm_503.py`
- `tests/test_tenant_isolation.py`
