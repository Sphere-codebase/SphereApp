from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")  # 10/20/2025


def _extract_labeled_date(soup: BeautifulSoup, label: str) -> str | None:
    """
    Try to find a date that appears near a label, e.g. "Next Review:".
    Returns the date string as MM/DD/YYYY (as on the page).
    """
    label_norm = _norm(label).rstrip(":")
    # Find any text node containing label (case-insensitive)
    for text_node in soup.find_all(string=True):
        t = _norm(str(text_node))
        if not t:
            continue
        if label_norm in t:
            # Try date in the same text node
            m = _DATE_RE.search(str(text_node))
            if m:
                return m.group(1)

            # Try dates in parent text (often label + date live in same container)
            parent = text_node.parent
            if parent:
                m2 = _DATE_RE.search(parent.get_text(" ", strip=True))
                if m2:
                    return m2.group(1)

                # Try next siblings (label in one node, date in next)
                for sib in parent.next_siblings:
                    if isinstance(sib, Tag):
                        m3 = _DATE_RE.search(sib.get_text(" ", strip=True))
                        if m3:
                            return m3.group(1)
                    else:
                        m3 = _DATE_RE.search(str(sib))
                        if m3:
                            return m3.group(1)
    return None


def _extract_policy_history_dates(soup: BeautifulSoup) -> dict[str, str | None]:
    """
    Best-effort extraction of Policy History dates.
    """
    # Try targeted extraction first
    last_review = _extract_labeled_date(soup, "Last Review")
    effective = _extract_labeled_date(soup, "Effective")
    next_review = _extract_labeled_date(soup, "Next Review")

    # Fallback: regex over full text if any missing
    full_text = soup.get_text(" ", strip=True)
    if not next_review:
        m = re.search(r"Next\s*Review[^0-9]*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.IGNORECASE)
        if m:
            next_review = m.group(1)
    if not last_review:
        m = re.search(r"Last\s*Review[^0-9]*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.IGNORECASE)
        if m:
            last_review = m.group(1)
    if not effective:
        m = re.search(r"Effective[^0-9]*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.IGNORECASE)
        if m:
            effective = m.group(1)

    return {
        "last_review": last_review,
        "effective": effective,
        "next_review": next_review,
    }


@dataclass
class AetnaCpbParseResult:
    source_url: str
    cpb_number: str | None
    cpb_type: str | None
    title: str | None
    medical_necessity_html: str
    medical_necessity_text: str
    # NEW
    last_review: str | None
    effective: str | None
    next_review: str | None


def parse_aetna_medical_necessity(html: str, *, source_url: str = "") -> AetnaCpbParseResult:
    soup = BeautifulSoup(html, "lxml")

    def meta(name: str) -> str | None:
        m = soup.find("meta", attrs={"name": name})
        if m and m.has_attr("content"):
            return str(m["content"]).strip() or None
        return None

    cpb_number = meta("aet.cpbNumber")
    cpb_type = meta("aet.cpbType")
    title = soup.title.get_text(strip=True) if soup.title else None

    # NEW: policy history dates
    ph = _extract_policy_history_dates(soup)

    # locate the H3
    h3 = None
    for cand in soup.find_all("h3"):
        if _norm(cand.get_text(" ", strip=True)) == "medical necessity":
            h3 = cand
            break
    if not h3:
        raise ValueError("Could not find 'Medical Necessity' heading in this page.")

    collected: list[Tag] = []
    for sib in h3.next_siblings:
        if isinstance(sib, Tag):
            if sib.name == "h3":
                break
            if sib.get_text(" ", strip=True):
                collected.append(sib)

    medical_html = "".join(str(x) for x in collected).strip()

    text_parts = [h3.get_text(" ", strip=True)]
    for node in collected:
        t = node.get_text(" ", strip=True)
        if t:
            text_parts.append(t)
    medical_text = "\n".join(text_parts).strip()

    if not medical_html or len(medical_text) < 30:
        raise ValueError("Medical Necessity block was found but looks empty/too short.")

    return AetnaCpbParseResult(
        source_url=source_url,
        cpb_number=cpb_number,
        cpb_type=cpb_type,
        title=title,
        medical_necessity_html=medical_html,
        medical_necessity_text=medical_text,
        last_review=ph["last_review"],
        effective=ph["effective"],
        next_review=ph["next_review"],
    )
