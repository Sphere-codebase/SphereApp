from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.parsers.pdf import pdf_parse


def parse_data(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Return a deterministic parse result for the provided PDF path."""
    result = pdf_parse.parse_data(input_path, output_path)
    if result is None and output_path.exists():
        return json.loads(output_path.read_text())
    if result is None:
        raise RuntimeError("Real PDF parser did not return output")
    if not output_path.exists():
        output_path.write_text(json.dumps(result, indent=2))
    return result
