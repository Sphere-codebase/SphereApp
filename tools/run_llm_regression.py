#!/usr/bin/env python3
"""Run local LLM/tool-call regression cases against the SphereApp API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_ENV_PATH = ROOT_DIR / ".env"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_CASES_PATH = "tests/llm_regression/cases.json"
DEFAULT_OUTPUT_ROOT = "artifacts/llm_regression"
DEFAULT_TIMEOUT_SECONDS = 120.0
SPHERE_BEARER_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxODA4NDkyMzI4fQ.ofLL4OTu8WBMkhcf0AL-47yI8_u4zCoERPv_sUkSY_U"
EMPTY_RESULT_PHRASES = (
    "no results",
    "no matching",
    "not found",
    "none found",
    "could not find",
    "unable to find",
)
TOOL_CALL_RE = re.compile(r"^\[tool_call\]\s+([A-Za-z0-9_]+)\s+args=(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Config:
    base_url: str
    email: str | None
    password: str | None
    bearer_token: str | None
    auth_mode: str
    cases_path: Path
    output_root: Path
    timeout_seconds: float
    baseline: Path | None
    enable_confirm_write: bool
    dotenv_path: Path
    dotenv_loaded: bool


def _strip_env_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_root_dotenv(path: Path = ROOT_ENV_PATH) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            print(f"skip malformed .env line {line_number}: missing '='", file=sys.stderr)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            print(f"skip malformed .env line {line_number}: invalid key", file=sys.stderr)
            continue
        value = _strip_env_quotes(value)
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _parse_float(value: str | None, *, default: float, label: str) -> float:
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise SystemExit(f"{label} must be a number, got: {value!r}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local LLM regression prompts against the SphereApp backend."
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument(
        "--bearer-token",
        default=None,
        help="Use an existing bearer token and skip /auth/login.",
    )
    parser.add_argument(
        "--cases-path",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output root. A timestamped run directory is created under this path.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
    )
    parser.add_argument("--baseline", default=None)
    parser.add_argument(
        "--enable-confirm-write",
        action="store_true",
        default=None,
        help="Enable case-configured confirm-action requests. Starter cases reject proposals.",
    )
    return parser.parse_args()


def _resolve_auth(args: argparse.Namespace) -> tuple[str | None, str | None, str | None, str]:
    if args.bearer_token:
        return None, None, args.bearer_token, "bearer_token"

    if args.email or args.password:
        email = args.email or _first_env("SPHERE_EMAIL", "EMAIL", "DEV_EMAIL")
        password = args.password or _first_env("SPHERE_PASSWORD", "PASSWORD", "DEV_PASSWORD")
        if email and password:
            return email, password, None, "login"
        raise SystemExit(
            "Missing login configuration. Pass both --email and --password, or set "
            "SPHERE_EMAIL/SPHERE_PASSWORD in the environment or root .env."
        )

    bearer_token = _first_env("SPHERE_BEARER_TOKEN")
    if bearer_token:
        return None, None, bearer_token, "bearer_token"

    email = _first_env("SPHERE_EMAIL")
    password = _first_env("SPHERE_PASSWORD")
    if email and password:
        return email, password, None, "login"

    email = _first_env("EMAIL", "DEV_EMAIL")
    password = _first_env("PASSWORD", "DEV_PASSWORD")
    if email and password:
        return email, password, None, "login"

    raise SystemExit(
        "Missing auth configuration. Set either SPHERE_BEARER_TOKEN or "
        "SPHERE_EMAIL/SPHERE_PASSWORD in the environment or root .env."
    )


def _load_config() -> Config:
    loaded_dotenv = _load_root_dotenv()
    args = _parse_args()
    email, password, bearer_token, auth_mode = _resolve_auth(args)

    base_url = (
        args.base_url
        or _first_env("SPHERE_BASE_URL")
        or _first_env("VITE_API_BASE_URL")
        or DEFAULT_BASE_URL
    )
    timeout_value = (
        str(args.timeout_seconds)
        if args.timeout_seconds is not None
        else _first_env("SPHERE_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS")
    )
    output_dir = args.output_dir or _first_env("SPHERE_OUTPUT_DIR") or DEFAULT_OUTPUT_ROOT
    cases_path = args.cases_path or _first_env("SPHERE_CASES_PATH") or DEFAULT_CASES_PATH
    baseline_raw = args.baseline or _first_env("SPHERE_BASELINE")
    enable_confirm_write = (
        bool(args.enable_confirm_write)
        if args.enable_confirm_write is not None
        else _env_bool("SPHERE_ENABLE_CONFIRM_WRITE", False)
    )

    return Config(
        base_url=str(base_url).rstrip("/"),
        email=email,
        password=password,
        bearer_token=bearer_token,
        auth_mode=auth_mode,
        cases_path=Path(cases_path),
        output_root=Path(output_dir),
        timeout_seconds=_parse_float(
            timeout_value,
            default=DEFAULT_TIMEOUT_SECONDS,
            label="timeout seconds",
        ),
        baseline=Path(baseline_raw) if baseline_raw else None,
        enable_confirm_write=enable_confirm_write,
        dotenv_path=ROOT_ENV_PATH,
        dotenv_loaded=bool(loaded_dotenv),
    )


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _safe_case_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "case"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"cases file not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid cases JSON: {path}: {exc}") from exc

    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise SystemExit("cases file must contain a list or an object with a 'cases' list")

    seen: set[str] = set()
    cases: list[dict[str, Any]] = []
    for index, case in enumerate(raw_cases, start=1):
        if not isinstance(case, dict):
            raise SystemExit(f"case #{index} must be an object")
        case_id = case.get("id")
        prompt = case.get("prompt")
        if not isinstance(case_id, str) or not case_id.strip():
            raise SystemExit(f"case #{index} is missing string id")
        if case_id in seen:
            raise SystemExit(f"duplicate case id: {case_id}")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"case {case_id} is missing prompt")
        seen.add(case_id)
        cases.append(case)
    return cases


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except json.JSONDecodeError:
        body = None
    return {
        "status_code": response.status_code,
        "headers": {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "x-request-id"}
        },
        "json": body,
        "text": response.text if body is None else None,
    }


def _post_json(
    client: httpx.Client,
    path: str,
    payload: dict[str, Any],
    token: str | None,
) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(path, json=payload, headers=headers)


def _get_json(client: httpx.Client, path: str, token: str) -> httpx.Response:
    return client.get(path, headers={"Authorization": f"Bearer {token}"})


def _authenticate(client: httpx.Client, config: Config, raw_dir: Path) -> str:
    if config.bearer_token:
        _write_json(
            raw_dir / "000_auth_mode.json",
            {
                "auth_mode": "bearer_token",
                "source": "SPHERE_BEARER_TOKEN or --bearer-token",
                "token": "<redacted>",
                "login_skipped": True,
            },
        )
        return config.bearer_token

    if not config.email or not config.password:
        raise SystemExit(
            "Missing auth configuration. Set either SPHERE_BEARER_TOKEN or "
            "SPHERE_EMAIL/SPHERE_PASSWORD in the environment or root .env."
        )

    request_payload = {"email": config.email, "password": "<redacted>"}
    _write_json(
        raw_dir / "000_auth_request.json",
        {"method": "POST", "path": "/auth/login", "json": request_payload},
    )
    response = _post_json(
        client,
        "/auth/login",
        {"email": config.email, "password": config.password},
        token=None,
    )
    response_payload = _response_payload(response)
    if isinstance(response_payload.get("json"), dict):
        response_payload["json"] = dict(response_payload["json"])
        if "access_token" in response_payload["json"]:
            response_payload["json"]["access_token"] = "<redacted>"
    _write_json(raw_dir / "000_auth_response.json", response_payload)

    if response.status_code != 200:
        raise SystemExit(f"auth failed with HTTP {response.status_code}; see raw auth artifacts")
    data = response.json()
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise SystemExit("auth response did not include access_token")
    return token


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _hash_payload(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def _looks_english(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return True
    cyrillic = sum(1 for char in letters if "\u0400" <= char <= "\u04ff")
    return (cyrillic / len(letters)) <= 0.15


def _tool_calls_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        match = TOOL_CALL_RE.match(content.strip())
        if not match:
            continue
        args_raw = match.group(2)
        try:
            args: Any = json.loads(args_raw)
        except json.JSONDecodeError:
            args = args_raw
        calls.append(
            {
                "message_id": message.get("id"),
                "tool": match.group(1),
                "arguments": args,
            }
        )
    return calls


def _validate(case: dict[str, Any], record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expect = case.get("expect") or {}
    if not isinstance(expect, dict):
        return ["expect must be an object"]

    expected_status = int(expect.get("expected_status", 200))
    if record.get("http_status") != expected_status:
        errors.append(f"expected HTTP {expected_status}, got {record.get('http_status')}")

    assistant = str(record.get("assistant_message") or "")
    tool_names = [item.get("tool") for item in record.get("tool_calls", [])]

    if "expected_action_required" in expect:
        expected = bool(expect["expected_action_required"])
        if bool(record.get("action_required")) is not expected:
            errors.append(
                f"expected action_required={expected}, got {record.get('action_required')}"
            )

    if "expected_proposed_changes" in expect:
        expected = bool(expect["expected_proposed_changes"])
        actual = record.get("proposed_changes") is not None
        if actual is not expected:
            errors.append(f"expected proposed_changes presence={expected}, got {actual}")

    if expect.get("expected_language") == "en" and not _looks_english(assistant):
        errors.append("expected English response, but response appears non-English")

    for substring in expect.get("required_substrings", []) or []:
        if not _contains(assistant, str(substring)):
            errors.append(f"missing required substring: {substring}")

    required_any = expect.get("required_any_substrings", []) or []
    if required_any and not any(_contains(assistant, str(item)) for item in required_any):
        errors.append(
            "missing at least one required substring: "
            + ", ".join(str(item) for item in required_any)
        )

    for substring in expect.get("forbidden_substrings", []) or []:
        if _contains(assistant, str(substring)):
            errors.append(f"found forbidden substring: {substring}")

    for section in expect.get("expected_sections", []) or []:
        if not _contains(assistant, str(section)):
            errors.append(f"missing expected section/label: {section}")

    for tool in expect.get("expected_tool_calls", []) or []:
        if tool not in tool_names:
            errors.append(f"missing expected tool call: {tool}")

    any_tools = expect.get("expected_any_tool_calls", []) or []
    if any_tools and not any(tool in tool_names for tool in any_tools):
        errors.append("missing at least one expected tool call: " + ", ".join(any_tools))

    for tool in expect.get("forbidden_tool_calls", []) or []:
        if tool in tool_names:
            errors.append(f"observed forbidden tool call: {tool}")

    if "min_tool_steps" in expect:
        debug = record.get("debug")
        if isinstance(debug, dict) and "tool_steps" in debug:
            try:
                actual_steps = int(debug.get("tool_steps") or 0)
            except (TypeError, ValueError):
                actual_steps = 0
            expected_steps = int(expect["min_tool_steps"])
            if actual_steps < expected_steps:
                errors.append(
                    f"expected at least {expected_steps} tool step(s), got {actual_steps}"
                )

    if expect.get("allow_empty_results") is False:
        lowered = assistant.lower()
        for phrase in EMPTY_RESULT_PHRASES:
            if phrase in lowered:
                errors.append(f"empty-result phrase not allowed: {phrase}")
                break

    return errors


def _fetch_session_messages(
    client: httpx.Client,
    token: str,
    session_id: int | None,
) -> tuple[int | None, list[dict[str, Any]], dict[str, Any]]:
    if session_id is None:
        return None, [], {"error": "session_id missing"}
    response = _get_json(client, f"/api/chat/sessions/{session_id}/messages", token)
    payload = _response_payload(response)
    messages = payload.get("json") if response.status_code == 200 else []
    if not isinstance(messages, list):
        messages = []
    return response.status_code, [item for item in messages if isinstance(item, dict)], payload


def _maybe_confirm_action(
    client: httpx.Client,
    token: str,
    case: dict[str, Any],
    record: dict[str, Any],
    raw_dir: Path,
    prefix: str,
    enable_confirm_write: bool,
) -> dict[str, Any] | None:
    confirm_config = case.get("confirm_action") or {}
    if not enable_confirm_write or not isinstance(confirm_config, dict):
        return None
    if not confirm_config.get("enabled"):
        return None
    proposed = record.get("proposed_changes")
    if not record.get("action_required") or not isinstance(proposed, dict):
        return {"skipped": True, "reason": "case did not return an action proposal"}

    tool = proposed.get("tool")
    if not isinstance(tool, str) or not tool:
        return {"skipped": True, "reason": "proposal did not include a tool"}

    request_payload = {
        "session_id": record.get("session_id"),
        "proposal_id": proposed.get("proposal_id"),
        "decision": confirm_config.get("decision", "reject"),
        "tool": tool,
        "arguments": proposed.get("arguments") or {},
        "payload": proposed.get("proposed_changes"),
    }
    _write_json(
        raw_dir / f"{prefix}_confirm_request.json",
        {"method": "POST", "path": "/api/chat/confirm-action", "json": request_payload},
    )
    started = time.perf_counter()
    response = _post_json(client, "/api/chat/confirm-action", request_payload, token)
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    response_payload = _response_payload(response)
    _write_json(raw_dir / f"{prefix}_confirm_response.json", response_payload)
    return {
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "decision": request_payload["decision"],
        "response": response_payload.get("json"),
    }


def _run_case(
    client: httpx.Client,
    token: str,
    case: dict[str, Any],
    index: int,
    raw_dir: Path,
    session_ids: dict[str, int],
    session_message_ids: dict[int, set[int]],
    enable_confirm_write: bool,
) -> dict[str, Any]:
    case_id = str(case["id"])
    prefix = f"{index:03d}_{_safe_case_id(case_id)}"
    session_group = case.get("session_group")
    session_id = session_ids.get(session_group) if isinstance(session_group, str) else None
    before_ids = (
        set(session_message_ids.get(session_id, set())) if session_id is not None else set()
    )
    request_payload: dict[str, Any] = {"message": case["prompt"]}
    if session_id is not None:
        request_payload["session_id"] = session_id

    request_artifact = {"method": "POST", "path": "/chat", "json": request_payload}
    request_ref = f"raw/{prefix}_request.json"
    response_ref = f"raw/{prefix}_response.json"
    messages_ref = f"raw/{prefix}_messages.json"
    _write_json(raw_dir / f"{prefix}_request.json", request_artifact)

    started_iso = _utc_iso()
    started = time.perf_counter()
    http_status: int | None = None
    response_json: Any = None
    transport_error: str | None = None
    response_payload: dict[str, Any]
    try:
        response = _post_json(client, "/chat", request_payload, token)
        http_status = response.status_code
        response_payload = _response_payload(response)
        response_json = response_payload.get("json")
    except httpx.HTTPError as exc:
        transport_error = str(exc)
        response_payload = {"error": transport_error}
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    ended_iso = _utc_iso()
    _write_json(raw_dir / f"{prefix}_response.json", response_payload)

    if isinstance(response_json, dict):
        raw_session_id = response_json.get("session_id")
        if isinstance(raw_session_id, int):
            session_id = raw_session_id
            if isinstance(session_group, str):
                session_ids[session_group] = raw_session_id

    messages_status, messages, messages_payload = _fetch_session_messages(client, token, session_id)
    _write_json(raw_dir / f"{prefix}_messages.json", messages_payload)
    current_ids = {item["id"] for item in messages if isinstance(item.get("id"), int)}
    if session_id is not None:
        session_message_ids[session_id] = current_ids
    new_messages = [item for item in messages if item.get("id") not in before_ids]
    tool_calls = _tool_calls_from_messages(new_messages)

    assistant_message = ""
    debug = None
    action_required = False
    proposed_changes = None
    ui_actions: list[Any] = []
    if isinstance(response_json, dict):
        assistant_message = str(response_json.get("assistant_message") or "")
        debug = response_json.get("debug")
        action_required = bool(response_json.get("action_required"))
        proposed_changes = response_json.get("proposed_changes")
        ui_actions_raw = response_json.get("ui_actions")
        ui_actions = ui_actions_raw if isinstance(ui_actions_raw, list) else []

    record: dict[str, Any] = {
        "case_id": case_id,
        "title": case.get("title"),
        "required": bool(case.get("required", True)),
        "session_group": session_group,
        "prompt": case["prompt"],
        "started_at": started_iso,
        "ended_at": ended_iso,
        "duration_ms": duration_ms,
        "http_status": http_status,
        "transport_error": transport_error,
        "raw_request_ref": request_ref,
        "raw_response_ref": response_ref,
        "raw_messages_ref": messages_ref,
        "messages_status": messages_status,
        "assistant_message": assistant_message,
        "normalized_assistant_message": _normalize_text(assistant_message),
        "assistant_output_hash": _hash_payload(_normalize_text(assistant_message)),
        "session_id": session_id,
        "ui_actions": ui_actions,
        "debug": debug,
        "action_required": action_required,
        "proposed_changes": proposed_changes,
        "proposed_changes_hash": _hash_payload(proposed_changes) if proposed_changes else None,
        "tool_calls": tool_calls,
        "tool_call_names": [item.get("tool") for item in tool_calls],
    }
    validation_errors = _validate(case, record)
    confirmation = _maybe_confirm_action(
        client,
        token,
        case,
        record,
        raw_dir,
        prefix,
        enable_confirm_write,
    )
    if confirmation is not None:
        record["confirmation"] = confirmation
    record["validation_errors"] = validation_errors
    record["passed"] = not validation_errors
    return record


def _load_baseline_records(path: Path) -> dict[str, dict[str, Any]]:
    results_path = path / "results.json" if path.is_dir() else path
    if not results_path.exists():
        raise SystemExit(f"baseline results not found: {results_path}")
    payload = json.loads(results_path.read_text())
    results = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        raise SystemExit(f"baseline file does not contain results list: {results_path}")
    return {
        str(item["case_id"]): item
        for item in results
        if isinstance(item, dict) and "case_id" in item
    }


def _compare_results(
    baseline_records: dict[str, dict[str, Any]],
    current_records: list[dict[str, Any]],
) -> str:
    current_by_id = {str(item["case_id"]): item for item in current_records}
    baseline_ids = set(baseline_records)
    current_ids = set(current_by_id)

    newly_passing: list[str] = []
    newly_failing: list[str] = []
    status_changes: list[str] = []
    action_changes: list[str] = []
    tool_changes: list[str] = []
    proposal_changes: list[str] = []
    output_changes: list[str] = []

    for case_id in sorted(baseline_ids & current_ids):
        old = baseline_records[case_id]
        new = current_by_id[case_id]
        if not old.get("passed") and new.get("passed"):
            newly_passing.append(case_id)
        if old.get("passed") and not new.get("passed"):
            newly_failing.append(case_id)
        if old.get("http_status") != new.get("http_status"):
            status_changes.append(
                f"{case_id}: {old.get('http_status')} -> {new.get('http_status')}"
            )
        if old.get("action_required") != new.get("action_required"):
            action_changes.append(
                f"{case_id}: {old.get('action_required')} -> {new.get('action_required')}"
            )
        old_tools = sorted(set(old.get("tool_call_names") or []))
        new_tools = sorted(set(new.get("tool_call_names") or []))
        if old_tools != new_tools:
            tool_changes.append(f"{case_id}: {old_tools} -> {new_tools}")
        if old.get("proposed_changes_hash") != new.get("proposed_changes_hash"):
            proposal_changes.append(
                f"{case_id}: {old.get('proposed_changes_hash')} -> "
                f"{new.get('proposed_changes_hash')}"
            )
        if old.get("assistant_output_hash") != new.get("assistant_output_hash"):
            output_changes.append(
                f"{case_id}: {old.get('assistant_output_hash')} -> "
                f"{new.get('assistant_output_hash')}"
            )

    lines = [
        "# Baseline Comparison",
        "",
        f"- Baseline cases: {len(baseline_ids)}",
        f"- Current cases: {len(current_ids)}",
        f"- Added cases: {', '.join(sorted(current_ids - baseline_ids)) or 'none'}",
        f"- Removed cases: {', '.join(sorted(baseline_ids - current_ids)) or 'none'}",
        "",
    ]
    sections = [
        ("Newly Passing", newly_passing),
        ("Newly Failing", newly_failing),
        ("HTTP Status Changes", status_changes),
        ("Action Required Changes", action_changes),
        ("Observed Tool Call Changes", tool_changes),
        ("Proposal Payload Hash Changes", proposal_changes),
        ("Assistant Output Hash Changes", output_changes),
    ]
    for title, rows in sections:
        lines.append(f"## {title}")
        if rows:
            lines.extend(f"- {row}" for row in rows)
        else:
            lines.append("- none")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_results(
    run_dir: Path,
    config: Config,
    cases_path: Path,
    results: list[dict[str, Any]],
) -> None:
    required = [item for item in results if item.get("required", True)]
    failed_required = [item for item in required if not item.get("passed")]
    passed = [item for item in results if item.get("passed")]
    failed = [item for item in results if not item.get("passed")]
    payload = {
        "generated_at": _utc_iso(),
        "summary": {
            "total": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "required": len(required),
            "failed_required": len(failed_required),
        },
        "results": results,
    }
    _write_json(run_dir / "results.json", payload)
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, sort_keys=True, default=str) + "\n")

    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "passed",
                "required",
                "http_status",
                "duration_ms",
                "session_id",
                "action_required",
                "tool_call_names",
                "validation_errors",
            ],
        )
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "case_id": item.get("case_id"),
                    "passed": item.get("passed"),
                    "required": item.get("required"),
                    "http_status": item.get("http_status"),
                    "duration_ms": item.get("duration_ms"),
                    "session_id": item.get("session_id"),
                    "action_required": item.get("action_required"),
                    "tool_call_names": ", ".join(item.get("tool_call_names") or []),
                    "validation_errors": " | ".join(item.get("validation_errors") or []),
                }
            )

    summary = _summary_markdown(config, cases_path, payload)
    _write_text(run_dir / "summary.md", summary)


def _summary_markdown(config: Config, cases_path: Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LLM Regression Summary",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Base URL: `{config.base_url}`",
        f"- Cases: `{cases_path}`",
        f"- Auth mode: `{config.auth_mode}`",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Failed required: {summary['failed_required']}",
        f"- Confirm write enabled: {config.enable_confirm_write}",
        "",
        "## Cases",
        "",
        "| Case | Status | HTTP | Tools | Errors |",
        "|---|---:|---:|---|---|",
    ]
    for item in payload["results"]:
        status = "PASS" if item.get("passed") else "FAIL"
        tools = ", ".join(item.get("tool_call_names") or [])
        errors = "<br>".join(item.get("validation_errors") or [])
        lines.append(
            f"| `{item.get('case_id')}` | {status} | {item.get('http_status')} | "
            f"{tools or '-'} | {errors or '-'} |"
        )
    failed = [item for item in payload["results"] if not item.get("passed")]
    if failed:
        lines.extend(["", "## Failure Detail", ""])
        for item in failed:
            lines.append(f"### `{item.get('case_id')}`")
            for error in item.get("validation_errors") or []:
                lines.append(f"- {error}")
            lines.append(f"- Raw response: `{item.get('raw_response_ref')}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_run_config(run_dir: Path, config: Config, cases: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": _utc_iso(),
        "base_url": config.base_url,
        "auth_mode": config.auth_mode,
        "bearer_token_set": bool(config.bearer_token),
        "email_set": bool(config.email),
        "password_set": bool(config.password),
        "cases_path": str(config.cases_path),
        "case_count": len(cases),
        "output_root": str(config.output_root),
        "run_dir": str(run_dir),
        "timeout_seconds": config.timeout_seconds,
        "baseline": str(config.baseline) if config.baseline else None,
        "enable_confirm_write": config.enable_confirm_write,
        "dotenv_path": str(config.dotenv_path),
        "dotenv_loaded": config.dotenv_loaded,
    }
    _write_json(run_dir / "run_config.json", payload)


def _print_resolved_config(config: Config) -> None:
    print("Resolved LLM regression config:")
    print(f"  base_url={config.base_url}")
    print(f"  cases_path={config.cases_path}")
    print(f"  output_root={config.output_root}")
    print(f"  timeout_seconds={config.timeout_seconds:g}")
    print(f"  baseline={config.baseline or '-'}")
    print(f"  enable_confirm_write={config.enable_confirm_write}")
    print(f"  dotenv={config.dotenv_path} loaded={config.dotenv_loaded}")
    if config.auth_mode == "bearer_token":
        print("  auth_mode=bearer_token token=<redacted>")
    else:
        print(
            "  auth_mode=login "
            f"email_set={bool(config.email)} password=<redacted>"
        )


def main() -> int:
    try:
        config = _load_config()
        cases = _load_cases(config.cases_path)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        print(exc, file=sys.stderr)
        return 2

    run_dir = config.output_root / _run_id()
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    _print_resolved_config(config)
    _write_run_config(run_dir, config, cases)

    timeout = httpx.Timeout(config.timeout_seconds)
    session_ids: dict[str, int] = {}
    session_message_ids: dict[int, set[int]] = {}
    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(base_url=config.base_url, timeout=timeout) as client:
            token = _authenticate(client, config, raw_dir)
            for index, case in enumerate(cases, start=1):
                result = _run_case(
                    client,
                    token,
                    case,
                    index,
                    raw_dir,
                    session_ids,
                    session_message_ids,
                    config.enable_confirm_write,
                )
                results.append(result)
                status = "PASS" if result["passed"] else "FAIL"
                print(f"{index:03d} {case['id']}: {status}")
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"HTTP setup error: {exc}", file=sys.stderr)
        return 2

    _write_results(run_dir, config, config.cases_path, results)

    if config.baseline:
        try:
            baseline_records = _load_baseline_records(config.baseline)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            return 2
        comparison = _compare_results(baseline_records, results)
        _write_text(run_dir / "compare_to_baseline.md", comparison)

    failed_required = [
        item for item in results if item.get("required", True) and not item.get("passed")
    ]
    print(f"\nArtifacts: {run_dir}")
    if failed_required:
        print(f"Failed required cases: {len(failed_required)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
