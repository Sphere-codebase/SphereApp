from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_SAMPLE_RESULT: dict[str, Any] = {
    "user_info": {
        "account_number": "060391381674",
        "name": "Lloyd Goldfarb",
        "date_of_birth": "10/15/1964",
    },
    "codes": [
        {
            "type": "RA",
            "code": "F1",
            "description": "Paid in full",
        }
    ],
    "info": [
        {
            "date": "07/09/2025",
            "cpt": "98925",
            "dx": ["M46.96"],
            "reason_codes": [],
            "billed_amount": "$1,000.00",
            "allowed_amount": "$120.00",
            "paid_amount": "$100.00",
            "ratio": 0.1,
            "adjustments": [
                {
                    "amount": "$3.81",
                    "type": "Patient Responsibility",
                    "code": "COIN",
                    "description": "Coinsurance",
                }
            ],
        },
        {
            "date": "07/09/2025",
            "cpt": "98926",
            "dx": ["M46.96"],
            "reason_codes": [],
            "billed_amount": "$1,000.00",
            "allowed_amount": "$110.00",
            "paid_amount": "$90.00",
            "ratio": 0.09,
            "adjustments": [
                {
                    "amount": "$30.00",
                    "type": "Patient Responsibility",
                    "code": "COIN",
                    "description": "Coinsurance",
                }
            ],
        },
        {
            "date": "07/09/2025",
            "cpt": "98927",
            "dx": ["M47.816"],
            "reason_codes": [],
            "billed_amount": "$900.00",
            "allowed_amount": "$112.34",
            "paid_amount": "$91.87",
            "ratio": 0.102,
            "adjustments": [
                {
                    "amount": "$30.00",
                    "type": "Patient Responsibility",
                    "code": "COIN",
                    "description": "Coinsurance",
                }
            ],
        },
        {
            "date": "07/09/2025",
            "cpt": "98928",
            "dx": ["M47.816"],
            "reason_codes": [],
            "billed_amount": "$800.00",
            "allowed_amount": "$110.00",
            "paid_amount": "$80.00",
            "ratio": 0.1,
            "adjustments": [
                {
                    "amount": "$26.66",
                    "type": "Patient Responsibility",
                    "code": "COIN",
                    "description": "Coinsurance",
                }
            ],
        },
    ],
}


def _load_real_parser() -> Any:
    override = os.getenv("PDF_PARSER_PATH", "").strip()
    if override:
        real_path = Path(override).expanduser()
    else:
        real_path = Path(__file__).resolve().parent / "pdf_parse.py"
    if real_path.resolve() == Path(__file__).resolve():
        raise RuntimeError("PDF_PARSER_PATH points to sample parser")
    if not real_path.exists():
        raise FileNotFoundError(f"Missing real PDF parser at {real_path}")
    spec = importlib.util.spec_from_file_location("dlc_modul_pdf_real_parser", real_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load parser module from {real_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    parse_fn = getattr(module, "parse_data", None)
    if parse_fn is None:
        parse_fn = getattr(module, "parse_pdf", None)
    if parse_fn is None:
        raise AttributeError("parse_data or parse_pdf not found in real parser module")
    return parse_fn


def parse_data(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Return a deterministic parse result for the provided PDF path."""
    # mode = os.getenv("PDF_PARSER_MODE", "").strip().lower()
    # if mode == "sample":
    #     output_path.write_text(json.dumps(_SAMPLE_RESULT, indent=2))
    #     return _SAMPLE_RESULT

    parse_fn = _load_real_parser()
    result = parse_fn(input_path, output_path)
    if result is None and output_path.exists():
        return json.loads(output_path.read_text())
    if result is None:
        raise RuntimeError("Real PDF parser did not return output")
    if not output_path.exists():
        output_path.write_text(json.dumps(result, indent=2))
    return result
