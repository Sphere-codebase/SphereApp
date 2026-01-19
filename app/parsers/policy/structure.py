from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


def _clean_ws(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s


def _li_text_without_nested_lists(li: Tag) -> str:
    """
    Extract text from <li> excluding text inside nested <ol>/<ul>.
    """
    li_clone = BeautifulSoup(str(li), "lxml").find("li")
    if not li_clone:
        return _clean_ws(li.get_text(" ", strip=True))

    # remove nested lists from clone
    for nested in li_clone.find_all(["ol", "ul"]):
        nested.decompose()

    return _clean_ws(li_clone.get_text(" ", strip=True))


def _parse_list(list_tag: Tag, id_prefix: str, level: int = 0) -> list[dict[str, Any]]:
    """
    Parse a <ol>/<ul> into items with children (recursive).
    """
    items: list[dict[str, Any]] = []
    lis = list_tag.find_all("li", recursive=False)

    for idx, li in enumerate(lis, start=1):
        item_id = f"{id_prefix}.{idx}" if level > 0 else f"{id_prefix}-{idx}"
        text = _li_text_without_nested_lists(li)

        # detect nested list
        nested = li.find(["ol", "ul"])
        children = _parse_list(nested, item_id, level + 1) if nested else []

        items.append(
            {
                "id": item_id,
                "level": level,
                "text": text,
                "children": children,
            }
        )
    return items


def _extract_notes(soup: BeautifulSoup) -> list[str]:
    """
    Extract 'Note:'/'Notes:' paragraphs.
    """
    notes: list[str] = []

    # Look for <strong>Note:</strong> or text starting with Note:
    for p in soup.find_all(["p", "div"]):
        t = _clean_ws(p.get_text(" ", strip=True))
        if not t:
            continue
        if re.match(r"^notes?:\s*", t, re.IGNORECASE):
            notes.append(t)
        elif re.search(r"\bnotes?:\b", t, re.IGNORECASE) and len(t) < 400:
            # sometimes "Note:" is inside a longer paragraph; keep it if short-ish
            notes.append(t)

    # dedupe while preserving order
    uniq: list[str] = []
    seen = set()
    for n in notes:
        if n not in seen:
            uniq.append(n)
            seen.add(n)
    return uniq


def _split_definitions_from_notes(notes: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    """
    Very light heuristic:
      if a note looks like 'For purposes of this policy, <term> is defined as ...'
      or contains 'is defined as', treat as definition.
    """
    defs: list[dict[str, str]] = []
    rest: list[str] = []

    for n in notes:
        m = re.search(r"\b([A-Za-z][A-Za-z\s/-]{2,40})\s+is defined as\b", n, re.IGNORECASE)
        if m:
            term = _clean_ws(m.group(1))
            defs.append({"term": term, "text": n})
        else:
            rest.append(n)

    return defs, rest


def build_structured_medical_necessity(medical_html: str) -> dict[str, Any]:
    """
    Returns a universal structured representation:

    {
      "criteria": [ {id, level, text, children[]} ... ],
      "notes": [ {text} ... ],
      "definitions": [ {term, text} ... ]
    }

    The key part: 'criteria' is derived from the first top-level list (<ol>/<ul>)
    found in the Medical Necessity HTML.
    """
    soup = BeautifulSoup(medical_html or "", "lxml")

    # Find the main list (first ol/ul that has direct li children)
    main_list: Tag | None = None
    for candidate in soup.find_all(["ol", "ul"]):
        if candidate.find("li", recursive=False):
            main_list = candidate
            break

    criteria: list[dict[str, Any]] = []
    if main_list:
        criteria = _parse_list(main_list, id_prefix="MN", level=0)
    else:
        # Fallback: no lists -> one single "criterion" block
        text = _clean_ws(soup.get_text(" ", strip=True))
        if text:
            criteria = [{"id": "MN-1", "level": 0, "text": text, "children": []}]

    notes_raw = _extract_notes(soup)
    definitions, notes_rest = _split_definitions_from_notes(notes_raw)

    return {
        "criteria": criteria,
        "notes": [{"text": t} for t in notes_rest],
        "definitions": definitions,
    }
