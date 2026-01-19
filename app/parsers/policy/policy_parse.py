from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.parsers.policy.dispatch import PARSERS
from app.parsers.policy.fetch import fetch_html
from app.parsers.policy.preprocess import preprocess_medical_necessity
from app.parsers.policy.structure import build_structured_medical_necessity

router = APIRouter(prefix="/api/policy", tags=["policy_parser"])


class PolicyParseRequest(BaseModel):
    url: HttpUrl
    payer_code: str


class PolicyParseResponse(BaseModel):
    payer_code: str
    source_url: str
    title: str | None
    next_review_iso: str | None
    medical_necessity_clean: str
    structured: dict[str, Any]


@router.post("/parse", response_model=PolicyParseResponse)
async def parse_policy_endpoint(payload: PolicyParseRequest) -> PolicyParseResponse:
    url_str = str(payload.url)
    payer_code = payload.payer_code.strip().lower()

    if payer_code not in PARSERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No parser available for payer: {payer_code}",
        )

    try:
        # 1. Fetch
        html = await fetch_html(url_str)

        # 2. Parse (Aetna CPB etc.)
        parser_func = PARSERS[payer_code]
        parsed = parser_func(html, source_url=url_str)

        # 3. Preprocess
        clean_text = preprocess_medical_necessity(parsed.medical_necessity_html)

        # 4. Structure
        structured = build_structured_medical_necessity(parsed.medical_necessity_html)

        return PolicyParseResponse(
            payer_code=payer_code,
            source_url=url_str,
            title=getattr(parsed, "title", None),
            next_review_iso=getattr(parsed, "next_review", None),
            medical_necessity_clean=clean_text,
            structured=structured,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {exc}",
        ) from exc
