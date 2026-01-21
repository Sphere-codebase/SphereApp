from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Shared client (connection pooling) ---
# If you have FastAPI lifespan events, you can close it on shutdown.
# This is a pragmatic minimal change to avoid creating a client per request.
_HTTPX_CLIENT: Optional[httpx.Client] = None


def _get_httpx_client() -> httpx.Client:
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None or hasattr(_HTTPX_CLIENT, "mock_calls"):
        # Split timeouts is safer than a single float in real networks.
        # 10s connect, settings-based read, 10s write, 10s pool wait.
        timeout = httpx.Timeout(
            connect=10.0,
            read=settings.pdf_parser_timeout_seconds,
            write=10.0,
            pool=10.0,
        )
        _HTTPX_CLIENT = httpx.Client(timeout=timeout)
    return _HTTPX_CLIENT


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class RemotePdfParserClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        retries: int | None = None,
        max_size: int | None = None,
        timeout_seconds: float | None = None,
        *,
        client: httpx.Client | None = None,
    ):
        self.base_url = (base_url or settings.pdf_parser_url or "").strip()
        self.api_key = (api_key or settings.pdf_parser_api_key or "").strip()
        self.retries = settings.pdf_parser_retries if retries is None else max(0, retries)
        self.max_size = (
            settings.pdf_parser_max_size_bytes if max_size is None else max(0, max_size)
        )
        self.timeout_seconds = (
            settings.pdf_parser_timeout_seconds
            if timeout_seconds is None
            else max(0.0, timeout_seconds)
        )
        self.client = client or _get_httpx_client()

        if not self.base_url:
            raise RuntimeError("pdf_parser_url is not configured")
        if not self.api_key:
            logger.warning("pdf_parser_api_key is not configured")

    def get_client(self) -> httpx.Client:
        return self.client or _get_httpx_client()

    def _raise_retry_exhausted(self) -> None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Remote PDF parser timed out after {self.retries} retries",
        )

    def parse_pdf(self, pdf_path: Path) -> dict[str, Any]:
        """
        Calls the remote PDF parser service to parse a PDF file.
        Returns a backward-compatible dict:
          { "pdf": <parse_result|None>, "error_message": <str|None>, "request_id": <str|None> }
        """
        if not pdf_path.exists() or not pdf_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF file does not exist: {pdf_path}",
            )

        url = f"{self.base_url.rstrip('/')}/v1/parse"
        logger.info("Calling remote PDF parser url=%s path=%s", url, pdf_path)

        # Prefer headers for auth; keep form-field fallback for compatibility
        headers = {
            "X-API-Key": self.api_key,
        }

        if self.max_size and pdf_path.stat().st_size > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"PDF too large (max {self.max_size} bytes)",
            )

        for attempt in range(self.retries + 1):
            try:
                client = self.get_client()
                with pdf_path.open("rb") as f:
                    files = {"file": (pdf_path.name, f, "application/pdf")}
                    data = {"x_api_key": self.api_key}  # fallback if remote expects it in form-data

                    response = client.post(url, files=files, data=data, headers=headers)

                # --- Error mapping & safe detail extraction ---
                if response.status_code == 422:
                    payload = _safe_json(response)
                    detail = None
                    if payload and isinstance(payload.get("detail"), (str, list, dict)):
                        detail = payload.get("detail")
                    else:
                        # fallback to raw text (may be HTML/plain)
                        detail = response.text[:2000] if response.text else "Unprocessable Entity"

                    logger.warning("Remote parser validation error: %s", detail)
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Remote parser validation error: {detail}",
                    )

                if response.status_code in (401, 403):
                    # Usually means misconfigured key or auth policy mismatch.
                    logger.error(
                        "Remote parser auth failed status=%s body=%s",
                        response.status_code,
                        (response.text[:2000] if response.text else ""),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Remote PDF parser authentication failed (check service key/config).",
                    )

                # Let httpx raise on other 4xx/5xx
                response.raise_for_status()

                result = _safe_json(response)
                if not result:
                    # Remote returned non-JSON or unexpected JSON shape
                    body_preview = response.text[:2000] if response.text else ""
                    logger.error(
                        "Remote parser returned non-JSON or invalid JSON. body=%s",
                        body_preview,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Remote PDF parser invalid response format (expected JSON).",
                    )

                parse_result = result.get("parse_result")
                request_id = result.get("request_id")

                # --- Contract validation ---
                if parse_result is None:
                    logger.error("Remote parser response missing parse_result. result=%s", result)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Remote PDF parser invalid response format (missing parse_result).",
                    )
                if not isinstance(parse_result, dict):
                    logger.error(
                        "Remote parser parse_result has invalid type: %s", type(parse_result)
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Remote PDF parser invalid response format (parse_result type).",
                    )

                return {
                    "pdf": parse_result,
                    "error_message": None,
                    "request_id": request_id,
                }

            except HTTPException:
                raise

            except httpx.TimeoutException:
                logger.exception("Remote PDF parser timeout attempt=%s", attempt + 1)
                if attempt < self.retries:
                    time.sleep(0.5)
                    continue
                self._raise_retry_exhausted()

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response else None
                if status_code is not None and status_code >= 500:
                    logger.warning(
                        "Remote PDF parser transient status=%s attempt=%s",
                        status_code,
                        attempt + 1,
                    )
                    if attempt < self.retries:
                        time.sleep(0.5)
                        continue
                    self._raise_retry_exhausted()

                logger.exception("Remote PDF parser request failed status=%s", status_code)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Remote PDF parser service error: {exc}",
                )

            except httpx.RequestError as exc:
                logger.exception("Remote PDF parser transport error attempt=%s", attempt + 1)
                if attempt < self.retries:
                    time.sleep(0.5)
                    continue
                self._raise_retry_exhausted()

            except Exception as exc:
                logger.exception("Unexpected error during PDF parsing")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Internal error during PDF parsing: {exc}",
                )


def parse_pdf_document(path: Path) -> dict[str, Any]:
    """Adapter function to maintain backward compatibility with old interface."""
    client = RemotePdfParserClient()
    return client.parse_pdf(path)


def close_remote_pdf_parser_http_client() -> None:
    """
    Optional helper: call on application shutdown if you have lifespan events.
    Example (FastAPI):
        @app.on_event("shutdown")
        def _shutdown():
            close_remote_pdf_parser_http_client()
    """
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is not None:
        try:
            _HTTPX_CLIENT.close()
        finally:
            _HTTPX_CLIENT = None
