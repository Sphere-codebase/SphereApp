"""Audit export helpers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable, Iterator, Sequence

PII_KEYS = {
    "email",
    "full_name",
    "first_name",
    "last_name",
    "phone",
    "primary_phone",
    "secondary_phone",
    "date_of_birth",
    "dob",
    "address",
    "line1",
    "line2",
    "zip",
    "chart_number",
}


def mask_pii(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, val in value.items():
            key_lower = str(key).lower()
            if key_lower in PII_KEYS:
                masked[key] = "***REDACTED***"
            else:
                masked[key] = mask_pii(val)
        return masked
    if isinstance(value, list):
        return [mask_pii(item) for item in value]
    return value


def diff_to_json(diff: Any) -> str:
    if diff is None:
        return ""
    return json.dumps(mask_pii(diff), default=str)


def iter_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
