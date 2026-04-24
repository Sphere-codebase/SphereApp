"""Normalization helpers for claim-related tool inputs."""

from __future__ import annotations

import re
from typing import Any

_CYRILLIC_LOOKALIKE_TRANSLATION = str.maketrans(
    {
        "С": "C",
        "с": "c",
        "Т": "T",
        "т": "t",
        "Р": "P",
        "р": "p",
        "К": "K",
        "к": "k",
    }
)
_PROCEDURE_CODE_PATTERN = re.compile(r"(?<!\d)(\d{5})(?!\d)")


def normalize_procedure_code(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    else:
        text = str(value).strip()
    if not text:
        return None
    normalized = text.translate(_CYRILLIC_LOOKALIKE_TRANSLATION)
    match = _PROCEDURE_CODE_PATTERN.search(normalized)
    if match is None:
        return None
    return match.group(1)
