#!/usr/bin/env python3
"""Simple concurrent endpoint probe for local latency checks."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    path: str
    status: int
    duration_ms: float


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def _auth_required(path: str) -> bool:
    return path not in {"/ready", "/health", "/api/status", "/"}


async def _hit(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    path: str,
    token: str | None,
) -> Sample:
    headers: dict[str, str] = {}
    if _auth_required(path) and token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.perf_counter()
    async with semaphore:
        response = await client.get(path, headers=headers)
    duration_ms = (time.perf_counter() - started) * 1000.0
    return Sample(path=path, status=response.status_code, duration_ms=duration_ms)


async def _run(args: argparse.Namespace) -> list[Sample]:
    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(args.timeout_seconds)
    samples: list[Sample] = []
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        for path in args.paths:
            if _auth_required(path) and not args.token:
                print(f"skip {path}: token required")
                continue
            tasks = [
                asyncio.create_task(_hit(client, semaphore, path, args.token))
                for _ in range(args.requests)
            ]
            samples.extend(await asyncio.gather(*tasks))
    return samples


def _print_summary(samples: list[Sample]) -> None:
    grouped: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.path].append(sample)

    for path in sorted(grouped):
        rows = grouped[path]
        durations = [row.duration_ms for row in rows]
        statuses = Counter(row.status for row in rows)
        print(f"\n{path}")
        print(f"  requests={len(rows)} statuses={dict(sorted(statuses.items()))}")
        print(f"  avg_ms={statistics.fmean(durations):.2f}")
        print(f"  p50_ms={_percentile(durations, 50):.2f}")
        print(f"  p95_ms={_percentile(durations, 95):.2f}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent probe for API endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=None)
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument(
        "--paths",
        default="/ready,/auth/me,/api/chat/sessions",
        type=lambda value: [item.strip() for item in value.split(",") if item.strip()],
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    samples = asyncio.run(_run(args))
    _print_summary(samples)


if __name__ == "__main__":
    main()
