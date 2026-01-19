"""Policy parser adapter (in-process)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException, status

from app.parsers.policy.dispatch import PARSERS
from app.parsers.policy.fetch import fetch_html
from app.parsers.policy.preprocess import preprocess_medical_necessity
from app.parsers.policy.structure import build_structured_medical_necessity


@dataclass(frozen=True)
class ParsedPolicy:
    payer_code: str
    source_url: str
    title: str | None
    next_review_iso: date | None
    medical_necessity_clean: str
    structured: dict[str, Any]


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        # Expected format from aetna_cpb.py is MM/DD/YYYY, which is not ISO.
        # However, ParsedPolicy expects next_review_iso as a date object.
        # Let's try to handle MM/DD/YYYY to date conversion.
        try:
            m, d, y = value.split("/")
            return date(int(y), int(m), int(d))
        except (ValueError, IndexError):
            return None


async def parse_policy(url: str, payer_code: str) -> ParsedPolicy:
    payer_code = payer_code.strip().lower()
    if payer_code not in PARSERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No parser available for payer: {payer_code}",
        )

    try:
        # 1. Fetch
        html = await fetch_html(url)

        # 2. Parse (Aetna CPB etc.)
        parser_func = PARSERS[payer_code]
        parsed = parser_func(html, source_url=url)

        # 3. Preprocess
        clean_text = preprocess_medical_necessity(parsed.medical_necessity_html)

        # 4. Structure
        structured = build_structured_medical_necessity(parsed.medical_necessity_html)

        return ParsedPolicy(
            payer_code=payer_code,
            source_url=url,
            title=getattr(parsed, "title", None),
            next_review_iso=_parse_iso_date(getattr(parsed, "next_review", None)),
            medical_necessity_clean=clean_text,
            structured=structured,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {exc}",
        ) from exc
