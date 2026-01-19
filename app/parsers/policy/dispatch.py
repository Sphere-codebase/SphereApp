from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.parsers.policy.aetna_cpb import parse_aetna_medical_necessity

PARSERS: dict[str, Callable[..., Any]] = {
    "aetna": parse_aetna_medical_necessity,
}
