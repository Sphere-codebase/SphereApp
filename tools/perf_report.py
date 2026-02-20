#!/usr/bin/env python3
"""Parse performance.log and print DB connection/request timing summaries."""

from __future__ import annotations

import argparse
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\w+\s+"
    r"path=(?P<path>\S+)\s+method=(?P<method>\S+)\s+status=(?P<status>\S+)\s+"
    r"duration_ms=(?P<duration>[0-9.\-]+)"
    r"(?:\s+sql_count=(?P<sql_count>[0-9\-]+))?"
    r"(?:\s+connect_created=(?P<connect_created>[a-z\-]+))?"
)

TARGET_ENDPOINTS = [
    "/auth/me",
    "/api/chat/sessions",
    "/api/chat/sessions/{id}/messages",
    "/api/admin/mcp-codes",
    "/api/admin/diagnosis-codes",
    "/api/admin/insurance-companies",
    "/ready",
]


def _normalize_path(path: str) -> str:
    if path.startswith("/api/chat/sessions/") and path.endswith("/messages"):
        return "/api/chat/sessions/{id}/messages"
    return path


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def _print_request_stats(name: str, values: list[float]) -> None:
    if not values:
        print(f"{name}: no samples")
        return
    print(
        f"{name}: count={len(values)} avg_ms={statistics.fmean(values):.2f} "
        f"p50_ms={_percentile(values, 50):.2f} p95_ms={_percentile(values, 95):.2f}"
    )


def _print_sql_stats(name: str, values: list[int]) -> None:
    if not values:
        print(f"{name}: no sql_count samples")
        return
    as_float = [float(value) for value in values]
    print(
        f"{name}: count={len(values)} avg_sql_count={statistics.fmean(as_float):.2f} "
        f"p50_sql_count={_percentile(as_float, 50):.2f} "
        f"p95_sql_count={_percentile(as_float, 95):.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize DB/connect/request metrics from performance.log"
    )
    parser.add_argument("--log", default="logs/performance.log")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        raise SystemExit(f"log file not found: {log_path}")

    connect_durations: list[float] = []
    connect_per_minute: Counter[str] = Counter()
    per_path: dict[str, list[float]] = defaultdict(list)
    per_path_sql_counts: dict[str, list[int]] = defaultdict(list)
    request_connect_created: Counter[str] = Counter()

    for raw in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = LINE_RE.match(raw)
        if not match:
            continue
        ts = match.group("ts")
        path = match.group("path")
        method = match.group("method")
        duration_raw = match.group("duration")
        sql_count_raw = match.group("sql_count")
        connect_created_raw = match.group("connect_created")
        if duration_raw == "-":
            continue
        duration = float(duration_raw)

        if method == "CONNECT":
            connect_durations.append(duration)
            connect_per_minute[ts[:16]] += 1
            continue

        if method != "GET":
            continue
        normalized_path = _normalize_path(path)
        per_path[normalized_path].append(duration)
        if sql_count_raw and sql_count_raw != "-":
            sql_count = int(sql_count_raw)
            per_path_sql_counts[normalized_path].append(sql_count)
        if connect_created_raw and connect_created_raw in {"true", "false"}:
            request_connect_created[connect_created_raw] += 1

    print("CONNECT summary")
    if connect_durations:
        print(
            f"count={len(connect_durations)} avg_ms={statistics.fmean(connect_durations):.2f} "
            f"p95_ms={_percentile(connect_durations, 95):.2f}"
        )
    else:
        print("count=0")

    print("\nCONNECT count per minute")
    if connect_per_minute:
        for minute, count in sorted(connect_per_minute.items()):
            print(f"{minute}: {count}")
    else:
        print("no CONNECT events")

    print("\nRequest durations")
    for endpoint in TARGET_ENDPOINTS:
        _print_request_stats(endpoint, per_path[endpoint])

    print("\nRequest SQL counts")
    for endpoint in TARGET_ENDPOINTS:
        _print_sql_stats(endpoint, per_path_sql_counts[endpoint])

    print("\nRequest connect_created")
    if request_connect_created:
        print(dict(sorted(request_connect_created.items())))
    else:
        print("no request connect_created samples")


if __name__ == "__main__":
    main()
