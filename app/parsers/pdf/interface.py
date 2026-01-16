"""PDF parser adapter for dlc-modul."""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SAMPLE_PARSER_PATH = _PROJECT_ROOT / "dlc-modul" / "aetna_pdf.py"
_DEFAULT_REAL_PARSER_PATH = _PROJECT_ROOT / "dlc-modul" / "pdf_parse.py"
_PARSE_FN: Callable[[Path, Path], dict[str, Any]] | None = None
_PARSE_PATH: Path | None = None
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


def _load_parser_module(path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(f"Missing parser file: {path}")
    spec = importlib.util.spec_from_file_location("dlc_modul_pdf_parser", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load parser module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_parser_path() -> tuple[Path, str]:
    mode = os.getenv("PDF_PARSER_MODE", "").strip().lower()
    if mode == "sample":
        return _SAMPLE_PARSER_PATH, "sample"
    path_override = os.getenv("PDF_PARSER_PATH")
    if path_override:
        return Path(path_override).expanduser(), "real"
    return _DEFAULT_REAL_PARSER_PATH, "real"


def _get_parse_fn() -> tuple[Callable[[Path, Path], dict[str, Any]], str, Path]:
    global _PARSE_FN, _PARSE_PATH
    path, backend = _resolve_parser_path()
    if _PARSE_FN is not None and _PARSE_PATH == path:
        return _PARSE_FN, backend, path
    module = _load_parser_module(path)
    parse_fn = getattr(module, "parse_data", None)
    if parse_fn is None:
        raise AttributeError("parse_data not found in parser module")
    _PARSE_FN = parse_fn
    _PARSE_PATH = path
    return parse_fn, backend, path


def parse_pdf_document(path: Path) -> dict[str, Any]:
    try:
        parse_fn, backend, parser_path = _get_parse_fn()
    except (FileNotFoundError, ImportError, AttributeError) as exc:
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
