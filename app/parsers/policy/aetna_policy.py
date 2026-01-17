"""Policy parser adapter for dlc-modul (local) or HTTP mode."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DLC_PARSERS_DIR = _PROJECT_ROOT / "dlc-modul" / "app" / "parsers"

_LOCAL_PARSERS: dict[str, Callable[..., Any]] | None = None
_PREPROCESS_FN: Callable[[str], str] | None = None
_STRUCTURE_FN: Callable[[str], dict[str, Any]] | None = None

_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PolicyParser/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_FETCH_TIMEOUT = httpx.Timeout(25.0, connect=10.0)


@dataclass(frozen=True)
class ParsedPolicy:
    payer_code: str
    source_url: str
    title: str | None
    next_review_iso: date | None
    medical_necessity_clean: str
    structured: dict[str, Any]


def _load_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise FileNotFoundError(f"Missing parser module: {name}") from exc


def _ensure_local_assets() -> tuple[
    dict[str, Callable[..., Any]],
    Callable[[str], str],
    Callable[[str], dict[str, Any]],
]:
    global _LOCAL_PARSERS, _PREPROCESS_FN, _STRUCTURE_FN

    if _LOCAL_PARSERS is None or _PREPROCESS_FN is None or _STRUCTURE_FN is None:
        if not _DLC_PARSERS_DIR.exists():
            raise FileNotFoundError("dlc-modul parser directory not found")

        aetna_module = _load_module("dlc_modul.app.parsers.aetna_cpb")
        preprocess_module = _load_module("dlc_modul.app.parsers.preprocess")
        structure_module = _load_module("dlc_modul.app.parsers.structure")

        _LOCAL_PARSERS = {"aetna": aetna_module.parse_aetna_medical_necessity}
        _PREPROCESS_FN = preprocess_module.preprocess_medical_necessity
        _STRUCTURE_FN = structure_module.build_structured_medical_necessity

    return _LOCAL_PARSERS, _PREPROCESS_FN, _STRUCTURE_FN


@retry(
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _fetch_html(url: str) -> str:
    with httpx.Client(
        headers=_FETCH_HEADERS,
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _parse_mmddyyyy(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_local(url: str, payer_code: str) -> ParsedPolicy:
    payer = payer_code.strip().lower()
    try:
        parsers, preprocess_fn, structure_fn = _ensure_local_assets()
    except (FileNotFoundError, ImportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Local parser module unavailable: {exc}",
        ) from exc

    parser = parsers.get(payer)
    if not parser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported payer_code='{payer_code}'.",
        )

    try:
        html = _fetch_html(url)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Policy fetch timed out: {exc}",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch page: {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch page: {exc}",
        ) from exc

    try:
        parsed = parser(html, source_url=url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive mapping
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parser crashed: {exc}",
        ) from exc

    next_review_iso = _parse_mmddyyyy(getattr(parsed, "next_review", None))
    medical_html = getattr(parsed, "medical_necessity_html", "") or ""
    try:
        medical_clean = preprocess_fn(medical_html)
    except Exception as exc:  # pragma: no cover - defensive mapping
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preprocess medical necessity: {exc}",
        ) from exc

    structured: dict[str, Any] = {}
    try:
        structured = structure_fn(medical_html)
    except Exception:
        structured = {}

    return ParsedPolicy(
        payer_code=payer,
        source_url=url,
        title=getattr(parsed, "title", None),
        next_review_iso=next_review_iso,
        medical_necessity_clean=medical_clean,
        structured=structured,
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
