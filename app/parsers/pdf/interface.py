"""PDF parser adapter for dlc-modul."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from app.parsers.pdf import aetna_eob, pdf_parse

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LEGACY_SAMPLE_PARSER_PATH = _PROJECT_ROOT / "dlc-modul" / "aetna_pdf.py"
_LEGACY_REAL_PARSER_PATH = _PROJECT_ROOT / "dlc-modul" / "pdf_parse.py"
_SAMPLE_PARSER_PATH = Path(__file__).resolve().parent / "aetna_eob.py"
_REAL_PARSER_PATH = Path(__file__).resolve().parent / "pdf_parse.py"
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


def _resolve_parser_backend() -> tuple[Callable[[Path, Path], dict[str, Any]], str, Path]:
    mode = os.getenv("PDF_PARSER_MODE", "").strip().lower()
    path_override = os.getenv("PDF_PARSER_PATH")
    if path_override:
        resolved = Path(path_override).expanduser().resolve()
        if resolved in {_LEGACY_SAMPLE_PARSER_PATH, _SAMPLE_PARSER_PATH}:
            return aetna_eob.parse_data, "sample", resolved
        if resolved in {_LEGACY_REAL_PARSER_PATH, _REAL_PARSER_PATH}:
            return pdf_parse.parse_data, "real", resolved
        raise FileNotFoundError(f"Unsupported parser path: {resolved}")
    if mode == "sample":
        return aetna_eob.parse_data, "sample", _SAMPLE_PARSER_PATH
    return pdf_parse.parse_data, "real", _REAL_PARSER_PATH


def parse_pdf_document(path: Path) -> dict[str, Any]:
    try:
        parse_fn, backend, parser_path = _resolve_parser_backend()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parser module unavailable: {exc}",
        ) from exc

    _logger.info("PDF parser backend=%s path=%s", backend, parser_path)
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
