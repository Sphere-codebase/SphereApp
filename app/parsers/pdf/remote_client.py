from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class RemotePdfParserClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or settings.pdf_parser_url
        self.api_key = api_key or settings.pdf_parser_api_key
        self.client = httpx.Client(timeout=60.0)

    def parse_pdf(self, pdf_path: Path) -> dict[str, Any]:
        """
        Calls the remote PDF parser service to parse a PDF file.
        """
        url = f"{self.base_url.rstrip('/')}/v1/parse"
        logger.info("Calling remote PDF parser url=%s path=%s", url, pdf_path)

        try:
            with pdf_path.open("rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                data = {"x_api_key": self.api_key}
                
                response = self.client.post(url, files=files, data=data)
                
            if response.status_code == 422:
                logger.error("Remote parser validation error: %s", response.text)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Remote parser validation error: {response.json().get('detail')}",
                )
            
            response.raise_for_status()
            result = response.json()
            
            # The remote service returns { "parse_result": { ... }, "request_id": "..." }
            # We want to return { "pdf": { ... }, "error_message": None } to maintain compatibility
            # with the previous interface.py output.
            
            return {
                "pdf": result.get("parse_result"),
                "error_message": None,
                "request_id": result.get("request_id")
            }

        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            logger.exception("Remote PDF parser request failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Remote PDF parser service error: {exc}",
            )
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
