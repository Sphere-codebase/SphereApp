"""Policy parser adapter (local or HTTP mode)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from fastapi import HTTPException, status
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings


@dataclass(frozen=True)
class ParsedPolicy:
    payer_code: str
    source_url: str
    title: str | None
    next_review_iso: date | None
    medical_necessity_clean: str
    structured: dict[str, Any]


def _ensure_local_assets() -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Local policy parser is unavailable in this build.",
    )


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_local(url: str, payer_code: str) -> ParsedPolicy:
    _ensure_local_assets()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Local policy parser is unavailable in this build.",
    )


@retry(
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_parse_request(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    timeout = httpx.Timeout(25.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        response = client.post("/api/policy/parse", json=payload)
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Parser error",
                request=response.request,
                response=response,
            )
        return response.json()


def _parse_http(url: str, payer_code: str) -> ParsedPolicy:
    payload = {"url": url, "payer_code": payer_code}
    try:
        data = _post_parse_request(settings.parser_base_url, payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Parser request timed out: {exc}",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else 502
        detail = None
        if exc.response is not None:
            try:
                detail = exc.response.json()
            except json.JSONDecodeError:
                detail = exc.response.text
        raise HTTPException(
            status_code=status_code,
            detail=detail or "Parser request failed",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Parser request failed: {exc}",
        ) from exc

    structured = data.get("structured") or {}
    return ParsedPolicy(
        payer_code=str(data.get("payer_code") or payer_code).strip().lower(),
        source_url=str(data.get("source_url") or url),
        title=data.get("title"),
        next_review_iso=_parse_iso_date(data.get("next_review_iso")),
        medical_necessity_clean=str(data.get("medical_necessity_clean") or ""),
        structured=structured,
    )


def parse_policy(url: str, payer_code: str) -> ParsedPolicy:
    mode = (settings.parser_mode or "local").lower()
    if mode == "http":
        return _parse_http(url, payer_code)
    return _parse_local(url, payer_code)
