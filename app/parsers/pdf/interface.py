"""PDF parser adapter."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from app.parsers.pdf import pdf_parse

_logger = logging.getLogger(__name__)


class PatientInfo(BaseModel):
    account_number: str | None = None
    name: str | None = None
    date_of_birth: str | None = None


class CodeInfo(BaseModel):
    type: str
    code: str
    description: str | None = None


class AdjustmentInfo(BaseModel):
    amount: str
    type: str
    code: str
    description: str | None = None


class ClaimInfo(BaseModel):
    date: str
    cpt: str
    dx: list[str]
    reason_codes: list[str]
    billed_amount: str
    allowed_amount: str
    paid_amount: str
    ratio: float
    adjustments: list[AdjustmentInfo]


class PdfInfo(BaseModel):
    user_info: PatientInfo
    codes: list[CodeInfo]
    info: list[ClaimInfo]


def parse_pdf_document(path: Path) -> dict[str, Any]:
    parse_fn = pdf_parse.parse_data
    _logger.info("PDF parser backend=pdf_parse")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / f"{path.stem}.json"
        try:
            result = parse_fn(path, output_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to parse PDF: {exc}",
            ) from exc

    try:
        PdfInfo.model_validate(result)
    except ValidationError as exc:
        return {"pdf": result, "error_message": str(exc)}

    return {"pdf": result, "error_message": None}
