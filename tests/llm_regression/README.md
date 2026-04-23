# LLM Regression Harness

This directory contains local-only regression cases for the SphereApp LLM and tool-calling claim workflow. The runner authenticates against the local FastAPI backend, sends chat prompts sequentially, captures raw request/response artifacts, writes normalized results, and can compare a run to a previous baseline.

The harness is intentionally external to production code. It does not modify chat routes, tool routing, or auth behavior.

## Prerequisites

Start the local backend first:

```bash
make run
```

The runner automatically loads the repository root `.env` file without overwriting already-set environment variables. The account must already exist, or you must provide a valid bearer token.

## Zero-Argument Local Run

```bash
python3 tools/run_llm_regression.py
```

This works when root `.env` contains enough auth configuration, for example either:

```bash
SPHERE_BEARER_TOKEN=ey...
```

or:

```bash
SPHERE_EMAIL=doctor@example.com
SPHERE_PASSWORD=your-local-password
```

If you prefer the virtualenv Python:

```bash
.venv/bin/python tools/run_llm_regression.py
```

The script prints the resolved non-secret config before running. Tokens and passwords are always redacted.

## Optional Overrides

```bash
SPHERE_BASE_URL="http://localhost:8000" \
SPHERE_CASES_PATH="tests/llm_regression/cases.json" \
SPHERE_OUTPUT_DIR="artifacts/llm_regression" \
SPHERE_TIMEOUT_SECONDS="120" \
python3 tools/run_llm_regression.py
```

CLI flags still take highest precedence:

```bash
python3 tools/run_llm_regression.py \
  --base-url "http://localhost:8000" \
  --timeout-seconds 120
```

## Baseline Comparison

Pass either a previous run directory or a previous `results.json`:

```bash
SPHERE_BASELINE="artifacts/llm_regression/20260423_120000" \
python3 tools/run_llm_regression.py
```

The runner writes `compare_to_baseline.md` in the new run directory. Comparison checks per-case pass/fail changes, HTTP status changes, `action_required` changes, observed tool-call changes, proposal payload hash changes, and assistant output hash changes.

## Auth Modes

Bearer-token mode skips `POST /auth/login` and uses the token directly:

```bash
SPHERE_BEARER_TOKEN="ey..." python3 tools/run_llm_regression.py
```

Login mode calls `POST /auth/login` once and reuses the returned token:

```bash
SPHERE_EMAIL="doctor@example.com" \
SPHERE_PASSWORD="your-local-password" \
python3 tools/run_llm_regression.py
```

You can also put either auth configuration in the root `.env`. If the repo has a dev user such as `doctor@example.com`, document its real local password in your private `.env`; do not commit credentials.

## Optional Confirmation Probe

By default, cases never call `POST /api/chat/confirm-action`. Enable it explicitly:

```bash
SPHERE_ENABLE_CONFIRM_WRITE="true" \
python3 tools/run_llm_regression.py
```

Starter write-flow cases use `decision: "reject"` so proposals are not committed. Keep confirm-enabled cases controlled and local-only.

## Config Resolution

The runner resolves config in this order:

- Explicit CLI args.
- Explicit `SPHERE_*` environment variables.
- Values loaded from repository root `.env`.
- Safe built-in defaults.

Important mappings:

- `SPHERE_BASE_URL` falls back to `.env` `VITE_API_BASE_URL`, then `http://localhost:8000`.
- `SPHERE_TIMEOUT_SECONDS` falls back to `.env` `LLM_TIMEOUT_SECONDS`, then `120`.
- `SPHERE_OUTPUT_DIR` defaults to `artifacts/llm_regression`.
- `SPHERE_ENABLE_CONFIRM_WRITE` defaults to `false`.
- Auth uses CLI auth values, then `SPHERE_BEARER_TOKEN`, then `SPHERE_EMAIL` plus `SPHERE_PASSWORD`, then dev-friendly `.env` names `EMAIL`/`PASSWORD` or `DEV_EMAIL`/`DEV_PASSWORD` if present.

The root `.env` loader only fills missing environment variables; it does not overwrite values already exported in your shell.

## Auth Error Example

If no token or login credentials are available, the runner exits before making chat requests:

```text
Missing auth configuration. Set either SPHERE_BEARER_TOKEN or SPHERE_EMAIL/SPHERE_PASSWORD in the environment or root .env.
```

Fix it by adding one of these to root `.env` or exporting it for one command:

```bash
SPHERE_BEARER_TOKEN=ey...
```

or:

```bash
SPHERE_EMAIL=doctor@example.com
SPHERE_PASSWORD=your-local-password
```

## Artifacts

Each run writes a timestamped directory under `artifacts/llm_regression/`:

- `run_config.json`: sanitized configuration. Passwords and tokens are never written.
- `results.json`: full normalized results plus aggregate counts.
- `results.jsonl`: one normalized result per line.
- `results.csv`: compact scan-friendly result table.
- `summary.md`: human-readable report.
- `raw/`: per-case raw chat requests, raw chat responses, session messages, and optional confirmation payloads.
- `compare_to_baseline.md`: only when `SPHERE_BASELINE` is set.

## Case Expectations

Cases live in `cases.json`. Supported expectation fields include:

- `expected_status`: exact HTTP status, default `200`.
- `expected_action_required`: expected `action_required` boolean.
- `expected_proposed_changes`: expected presence of `proposed_changes`.
- `expected_language`: currently supports `en` with a simple Cyrillic-ratio guard.
- `required_substrings`: all substrings must appear in assistant text.
- `required_any_substrings`: at least one substring must appear in assistant text.
- `forbidden_substrings`: substrings that must not appear in assistant text.
- `expected_sections`: headings or labels expected in assistant text.
- `expected_tool_calls`: all listed tool calls must be observed.
- `expected_any_tool_calls`: at least one listed tool call must be observed.
- `forbidden_tool_calls`: listed tool calls must not be observed.
- `min_tool_steps`: checks `debug.tool_steps` when the backend exposes debug.
- `allow_empty_results`: when `false`, fails on common empty-result phrases.

The runner captures observable tool calls by reading persisted chat session messages and parsing assistant messages like `[tool_call] get_claim args={...}`. Tool result rows are not exposed by the session messages endpoint, so raw chat responses and parsed tool calls are preserved for offline review.

## Exit Codes

- `0`: all required cases passed.
- `1`: one or more required cases failed.
- `2`: setup, auth, cases-file, or baseline configuration error.

## Notes

The starter suite centers on CPT `62323` and claim-preparation behavior, but it does not assume your local database contains code `62323`, `Jane Doe`, or any specific claim id. Prompts ask the assistant to report missing database-backed facts rather than guess.
