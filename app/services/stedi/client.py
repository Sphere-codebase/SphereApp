"""Stedi Claim Status API client."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

CLAIM_STATUS_PATH = "/change/medicalnetwork/claimstatus/v2"


@dataclass(frozen=True)
class NormalizedClaimStatus:
    status: str
    status_code: str | None
    status_category: str | None
    message: str
    amount_paid: Decimal | None
    payer_claim_number: str | None
    trace_id: str | None
    claim_count: int


@dataclass(frozen=True)
class StediClaimStatusSuccess:
    http_status_code: int
    status: NormalizedClaimStatus
    response_summary: dict[str, Any]


@dataclass(frozen=True)
class StediClaimStatusError:
    http_status_code: int | None
    error_code: str
    message: str
    trace_id: str | None = None
    response_summary: dict[str, Any] | None = None


StediClaimStatusResult = StediClaimStatusSuccess | StediClaimStatusError


class StediClaimStatusClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_seconds)

    def check_claim_status(self, payload: dict[str, Any]) -> StediClaimStatusResult:
        url = f"{self._base_url}{CLAIM_STATUS_PATH}"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return StediClaimStatusError(
                http_status_code=None,
                error_code="STEDI_TIMEOUT",
                message="Stedi claim status request timed out.",
            )
        except httpx.HTTPError:
            return StediClaimStatusError(
                http_status_code=None,
                error_code="STEDI_NETWORK_ERROR",
                message="Stedi claim status service could not be reached.",
            )

        body = _safe_json(response)
        trace_id = _extract_trace_id(body)
        if response.status_code >= 400:
            return StediClaimStatusError(
                http_status_code=response.status_code,
                error_code="STEDI_HTTP_ERROR",
                message="Stedi returned an error while checking claim status.",
                trace_id=trace_id,
                response_summary=_summarize_response(body, response.status_code),
            )

        normalized = _normalize_claim_status(body, response.status_code)
        return StediClaimStatusSuccess(
            http_status_code=response.status_code,
            status=normalized,
            response_summary=_summarize_response(body, response.status_code),
        )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _extract_trace_id(body: dict[str, Any]) -> str | None:
    meta = body.get("meta")
    if isinstance(meta, dict):
        trace_id = meta.get("traceId")
        if isinstance(trace_id, str) and trace_id:
            return trace_id
    transaction = body.get("transactionIdentifier")
    if isinstance(transaction, dict):
        transaction_id = transaction.get("transactionId")
        if isinstance(transaction_id, str) and transaction_id:
            return transaction_id
    return None


def _normalize_claim_status(body: dict[str, Any], http_status_code: int) -> NormalizedClaimStatus:
    claims = body.get("claims")
    claim_items = claims if isinstance(claims, list) else []
    trace_id = _extract_trace_id(body)
    if not claim_items:
        return NormalizedClaimStatus(
            status="NO_MATCH",
            status_code=None,
            status_category=None,
            message="No matching payer claim status was returned.",
            amount_paid=None,
            payer_claim_number=None,
            trace_id=trace_id,
            claim_count=0,
        )

    claim_status = claim_items[0].get("claimStatus") if isinstance(claim_items[0], dict) else {}
    claim_status = claim_status if isinstance(claim_status, dict) else {}
    status_category = _string_or_none(claim_status.get("statusCategoryCode"))
    status_code = _string_or_none(claim_status.get("statusCode"))
    category_text = _string_or_none(claim_status.get("statusCategoryCodeValue"))
    code_text = _string_or_none(claim_status.get("statusCodeValue"))
    message = code_text or category_text or "Claim status returned by payer."
    status = _derive_status(status_category, status_code, message, http_status_code)
    return NormalizedClaimStatus(
        status=status,
        status_code=status_code,
        status_category=status_category,
        message=message,
        amount_paid=_decimal_or_none(claim_status.get("amountPaid")),
        payer_claim_number=_string_or_none(claim_status.get("tradingPartnerClaimNumber")),
        trace_id=trace_id,
        claim_count=len(claim_items),
    )


def _derive_status(
    status_category: str | None,
    status_code: str | None,
    message: str,
    http_status_code: int,
) -> str:
    text = f"{status_category or ''} {status_code or ''} {message}".lower()
    if "denied" in text or "reject" in text:
        return "DENIED"
    if "paid" in text or "payment" in text:
        return "PAID"
    if "finalized" in text or "final" in text:
        return "FINAL"
    if http_status_code == 200:
        return "SUBMITTED"
    return "UNKNOWN"


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _summarize_response(body: dict[str, Any], http_status_code: int) -> dict[str, Any]:
    claims = body.get("claims")
    claim_items = claims if isinstance(claims, list) else []
    status_codes: list[str] = []
    status_categories: list[str] = []
    for item in claim_items:
        if not isinstance(item, dict):
            continue
        claim_status = item.get("claimStatus")
        if not isinstance(claim_status, dict):
            continue
        status_code = _string_or_none(claim_status.get("statusCode"))
        status_category = _string_or_none(claim_status.get("statusCategoryCode"))
        if status_code:
            status_codes.append(status_code)
        if status_category:
            status_categories.append(status_category)
    return {
        "http_status_code": http_status_code,
        "claim_count": len(claim_items),
        "status_codes": status_codes,
        "status_categories": status_categories,
        "trace_id": _extract_trace_id(body),
    }
