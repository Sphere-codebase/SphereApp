#!/usr/bin/env python3
"""Interactive launcher for the local LLM regression runner."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT_DIR / "tools" / "run_llm_regression.py"
CASES_PATH = ROOT_DIR / "tests" / "llm_regression" / "cases.json"
ARTIFACTS_ROOT = ROOT_DIR / "artifacts" / "llm_regression"

FALLBACK_TOOL_MAP: dict[str, tuple[str, ...]] = {
    "get_bot_capabilities": ("capability_discovery",),
    "time_now": ("time_now",),
    "get_account": ("current_account",),
    "search_patients": ("search_patient_by_name", "fetch_patient_details_after_search"),
    "get_patient": ("fetch_patient_details_after_search",),
    "list_claims": ("list_recent_claims",),
    "get_claim": ("open_and_summarize_claim",),
    "get_procedure_code": ("identify_code_62323",),
    "list_procedure_codes": ("identify_code_62323",),
    "list_policy_links_for_code": ("policy_links_62323",),
    "get_policy_rules_for_link": ("latest_policy_rules_62323",),
    "explain_coverage_for_code": ("coverage_explain_62323",),
    "create_claim_draft": ("create_claim_draft_proposal",),
    "update_claim_fields": ("update_claim_fields_proposal",),
}

TOOL_PACKS: dict[str, tuple[str, ...]] = {
    "capabilities": (
        "basic_greeting",
        "capability_discovery",
        "time_now",
        "current_account",
    ),
    "patients": (
        "search_patient_by_name",
        "fetch_patient_details_after_search",
    ),
    "claims": (
        "list_recent_claims",
        "open_and_summarize_claim",
    ),
    "coverage_policy": (
        "identify_code_62323",
        "policy_links_62323",
        "latest_policy_rules_62323",
        "coverage_explain_62323",
        "guardrail_no_fabricated_policy",
    ),
    "claim_drafting": (
        "medical_necessity_evidence_check",
        "list_present_information",
        "list_missing_information",
        "minimum_followup_questions",
        "draft_readiness_decision",
        "create_claim_draft_proposal",
        "update_claim_fields_proposal",
    ),
}


def _load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise SystemExit(f"invalid cases file: {path}")
    cases = [case for case in raw_cases if isinstance(case, dict)]
    if not cases:
        raise SystemExit(f"no cases found: {path}")
    return cases


def _case_id_order(cases: list[dict[str, Any]]) -> list[str]:
    return [str(case["id"]) for case in cases]


def _normalize_case_ids(cases: list[dict[str, Any]], case_ids: list[str]) -> list[str]:
    order = _case_id_order(cases)
    selected = set(case_ids)
    return [case_id for case_id in order if case_id in selected]


def _case_tools(case: dict[str, Any], fallback_by_case: dict[str, list[str]]) -> list[str]:
    expect = case.get("expect")
    tools: list[str] = []
    if isinstance(expect, dict):
        for key in ("expected_tool_calls", "expected_any_tool_calls"):
            values = expect.get(key) or []
            if isinstance(values, list):
                tools.extend(str(value) for value in values if str(value).strip())
    tools.extend(fallback_by_case.get(str(case["id"]), []))
    deduped: list[str] = []
    seen: set[str] = set()
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            deduped.append(tool)
    return deduped


def _build_tool_map(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    case_ids = {str(case["id"]) for case in cases}
    for case in cases:
        expect = case.get("expect")
        if not isinstance(expect, dict):
            continue
        for key in ("expected_tool_calls", "expected_any_tool_calls"):
            values = expect.get(key) or []
            if not isinstance(values, list):
                continue
            for value in values:
                tool_name = str(value).strip()
                if not tool_name:
                    continue
                mapping.setdefault(tool_name, []).append(str(case["id"]))
    for tool_name, fallback_case_ids in FALLBACK_TOOL_MAP.items():
        bucket = mapping.setdefault(tool_name, [])
        for case_id in fallback_case_ids:
            if case_id in case_ids and case_id not in bucket:
                bucket.append(case_id)
    order = _case_id_order(cases)
    for tool_name, selected_ids in list(mapping.items()):
        selected = set(selected_ids)
        mapping[tool_name] = [case_id for case_id in order if case_id in selected]
    return dict(sorted(mapping.items()))


def _build_fallback_by_case(tool_map: dict[str, list[str]]) -> dict[str, list[str]]:
    fallback_by_case: dict[str, list[str]] = {}
    for tool_name, case_ids in FALLBACK_TOOL_MAP.items():
        known_case_ids = set(tool_map.get(tool_name, []))
        for case_id in case_ids:
            if case_id in known_case_ids:
                fallback_by_case.setdefault(case_id, []).append(tool_name)
    return fallback_by_case


def _build_session_group_map(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for case in cases:
        session_group = case.get("session_group")
        if isinstance(session_group, str) and session_group.strip():
            mapping.setdefault(session_group, []).append(str(case["id"]))
    return dict(sorted(mapping.items()))


def _latest_run_dirs(limit: int = 10) -> list[Path]:
    if not ARTIFACTS_ROOT.exists():
        return []
    run_dirs = [path for path in ARTIFACTS_ROOT.iterdir() if path.is_dir()]
    run_dirs.sort(reverse=True)
    return run_dirs[:limit]


def _print_header() -> None:
    print("\nLLM Regression Menu")
    print(f"Repo root: {ROOT_DIR}")
    print(f"Cases file: {CASES_PATH.relative_to(ROOT_DIR)}")
    print(f"Artifacts root: {ARTIFACTS_ROOT.relative_to(ROOT_DIR)}")


def _print_cases(cases: list[dict[str, Any]], fallback_by_case: dict[str, list[str]]) -> None:
    print("\nAvailable cases:")
    for index, case in enumerate(cases, start=1):
        case_id = str(case["id"])
        title = str(case.get("title") or "-")
        session_group = str(case.get("session_group") or "-")
        tools = ", ".join(_case_tools(case, fallback_by_case)) or "-"
        print(
            f"{index:>2}. {case_id}"
            f"\n    title={title}"
            f"\n    session_group={session_group}"
            f"\n    tools={tools}"
        )


def _prompt(message: str) -> str:
    return input(message).strip()


def _resolve_case_token(
    token: str,
    cases: list[dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
) -> str | None:
    if token.isdigit():
        index = int(token)
        if 1 <= index <= len(cases):
            return str(cases[index - 1]["id"])
    return token if token in cases_by_id else None


def _parse_case_selection(
    raw_value: str,
    cases: list[dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    tokens = [token.strip() for token in raw_value.split(",") if token.strip()]
    if not tokens:
        raise ValueError("no case selection provided")
    selected_ids: list[str] = []
    seen: set[str] = set()
    invalid: list[str] = []
    for token in tokens:
        case_id = _resolve_case_token(token, cases, cases_by_id)
        if case_id is None:
            invalid.append(token)
            continue
        if case_id not in seen:
            seen.add(case_id)
            selected_ids.append(case_id)
    if invalid:
        raise ValueError(f"unknown case selection(s): {', '.join(invalid)}")
    return _normalize_case_ids(cases, selected_ids)


def _choose_named_option(options: list[str], label: str) -> str | None:
    if not options:
        print(f"No {label} options available.")
        return None
    print(f"\nAvailable {label}:")
    for index, option in enumerate(options, start=1):
        print(f"{index:>2}. {option}")
    raw_value = _prompt(f"Select {label} by number or name: ")
    if not raw_value:
        return None
    if raw_value.isdigit():
        index = int(raw_value)
        if 1 <= index <= len(options):
            return options[index - 1]
    if raw_value in options:
        return raw_value
    print(f"Unknown {label}: {raw_value}")
    return None


def _choose_failed_only_path(last_from_run: Path | None) -> Path | None:
    latest_runs = _latest_run_dirs()
    if latest_runs:
        print("\nRecent run directories:")
        for index, path in enumerate(latest_runs, start=1):
            print(f"{index:>2}. {path.relative_to(ROOT_DIR)}")
    default_path = last_from_run or (latest_runs[0] if latest_runs else None)
    prompt = "Previous run dir or results.json path"
    if default_path is not None:
        prompt += f" [{default_path}]"
    prompt += ": "
    raw_value = _prompt(prompt)
    if not raw_value and default_path is not None:
        return default_path
    if raw_value.isdigit() and latest_runs:
        index = int(raw_value)
        if 1 <= index <= len(latest_runs):
            return latest_runs[index - 1]
    if not raw_value:
        print("No previous run path provided.")
        return None
    candidate = Path(raw_value)
    if not candidate.is_absolute():
        candidate = (ROOT_DIR / candidate).resolve()
    if not candidate.exists():
        print(f"Path not found: {candidate}")
        return None
    return candidate


def _build_command(extra_args: list[str]) -> list[str]:
    return [sys.executable, str(RUNNER_PATH), *extra_args]


def _confirm_and_run(command: list[str], selection_label: str) -> int:
    print("\nAbout to run:")
    print(f"  selection: {selection_label}")
    print(f"  artifacts: {ARTIFACTS_ROOT.relative_to(ROOT_DIR)}")
    print(f"  command: {shlex.join(command)}")
    if _prompt("Launch this run? [y/N]: ").lower() not in {"y", "yes"}:
        print("Canceled.")
        return 0
    print("")
    result = subprocess.run(command, cwd=ROOT_DIR, check=False)
    print(f"\nRunner exit code: {result.returncode}")
    return result.returncode


def _select_one_case(
    cases: list[dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
    fallback_by_case: dict[str, list[str]],
) -> list[str] | None:
    _print_cases(cases, fallback_by_case)
    raw_value = _prompt("Select one case by number or case_id: ")
    if not raw_value:
        return None
    try:
        selected = _parse_case_selection(raw_value, cases, cases_by_id)
    except ValueError as exc:
        print(exc)
        return None
    if len(selected) != 1:
        print("Select exactly one case.")
        return None
    return selected


def _select_multiple_cases(
    cases: list[dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
    fallback_by_case: dict[str, list[str]],
) -> list[str] | None:
    _print_cases(cases, fallback_by_case)
    raw_value = _prompt("Select multiple cases by comma-separated numbers or case_ids: ")
    if not raw_value:
        return None
    try:
        return _parse_case_selection(raw_value, cases, cases_by_id)
    except ValueError as exc:
        print(exc)
        return None


def _case_args(case_ids: list[str]) -> list[str]:
    args: list[str] = []
    for case_id in case_ids:
        args.extend(["--case-id", case_id])
    return args


def main() -> int:
    cases = _load_cases()
    cases_by_id = {str(case["id"]): case for case in cases}
    tool_map = _build_tool_map(cases)
    fallback_by_case = _build_fallback_by_case(tool_map)
    session_group_map = _build_session_group_map(cases)
    last_from_run: Path | None = None

    while True:
        _print_header()
        print(
            "\n"
            "1. Run all cases\n"
            "2. Run failed-only from a previous run\n"
            "3. Run one case by case_id\n"
            "4. Run multiple selected case_ids\n"
            "5. Run all cases from a session_group\n"
            "6. Run all cases related to a tool name or tool-focused pack\n"
            "7. List available cases and exit\n"
            "8. Exit\n"
        )
        choice = _prompt("Choose an option: ")

        if choice == "1":
            _confirm_and_run(_build_command([]), "all cases")
            continue

        if choice == "2":
            from_run = _choose_failed_only_path(last_from_run)
            if from_run is None:
                continue
            last_from_run = from_run
            args = ["--failed-only", "--from-run", str(from_run)]
            _confirm_and_run(_build_command(args), f"failed-only from {from_run}")
            continue

        if choice == "3":
            selected = _select_one_case(cases, cases_by_id, fallback_by_case)
            if not selected:
                continue
            _confirm_and_run(_build_command(_case_args(selected)), f"one case: {selected[0]}")
            continue

        if choice == "4":
            selected = _select_multiple_cases(cases, cases_by_id, fallback_by_case)
            if not selected:
                continue
            _confirm_and_run(
                _build_command(_case_args(selected)),
                f"multiple cases: {', '.join(selected)}",
            )
            continue

        if choice == "5":
            session_group = _choose_named_option(list(session_group_map), "session_group")
            if session_group is None:
                continue
            selected = session_group_map[session_group]
            _confirm_and_run(
                _build_command(_case_args(selected)),
                f"session_group {session_group}: {', '.join(selected)}",
            )
            continue

        if choice == "6":
            print("\n1. Select by tool name\n2. Select a tool-focused pack\n3. Back")
            subchoice = _prompt("Choose a sub-option: ")
            if subchoice == "1":
                tool_name = _choose_named_option(list(tool_map), "tool")
                if tool_name is None:
                    continue
                selected = tool_map[tool_name]
                _confirm_and_run(
                    _build_command(_case_args(selected)),
                    f"tool {tool_name}: {', '.join(selected)}",
                )
                continue
            if subchoice == "2":
                pack_name = _choose_named_option(list(TOOL_PACKS), "tool pack")
                if pack_name is None:
                    continue
                selected = _normalize_case_ids(cases, list(TOOL_PACKS[pack_name]))
                _confirm_and_run(
                    _build_command(_case_args(selected)),
                    f"tool pack {pack_name}: {', '.join(selected)}",
                )
                continue
            continue

        if choice == "7":
            _print_cases(cases, fallback_by_case)
            return 0

        if choice == "8":
            return 0

        print(f"Unknown option: {choice}")


if __name__ == "__main__":
    raise SystemExit(main())
