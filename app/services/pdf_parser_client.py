"""PDF parser adapter for dlc-modul."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

_PARSER_PATH = Path(__file__).resolve().parents[2] / "dlc-modul" / "aetna_pdf.py"
_PARSE_FN: Callable[[Path, Path], dict[str, Any]] | None = None


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


def _load_parser_module() -> ModuleType:
    if not _PARSER_PATH.exists():
        raise FileNotFoundError(f"Missing parser file: {_PARSER_PATH}")
    spec = importlib.util.spec_from_file_location("dlc_modul_pdf_parser", _PARSER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load parser module from {_PARSER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _get_parse_fn() -> Callable[[Path, Path], dict[str, Any]]:
    global _PARSE_FN
    if _PARSE_FN is not None:
        return _PARSE_FN
    module = _load_parser_module()
    parse_fn = getattr(module, "parse_data", None)
    if parse_fn is None:
        raise AttributeError("parse_data not found in parser module")
    _PARSE_FN = parse_fn
    return parse_fn


def parse_pdf_document(path: Path) -> dict[str, Any]:
    try:
        parse_fn = _get_parse_fn()
    except (FileNotFoundError, ImportError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parser module unavailable: {exc}",
        ) from exc

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
