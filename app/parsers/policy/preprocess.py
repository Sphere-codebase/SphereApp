from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

# Убираем только "(1) (2) (3)" когда это похоже на маркер списка.
# НЕ трогаем "(2) weeks", "(12) months", "(50%)" и т.п.
_UNIT_AFTER_PARENS_RE = re.compile(
    r"\(\s*\d+\s*\)\s*(weeks?|months?|years?|days?|sessions?|levels?|times?|%|tfesis?|inches?|cm|mm)\b",
    re.IGNORECASE,
)
_LIST_MARKER_PARENS_RE = re.compile(r"\(\s*\d+\s*\)(?=\s*(?:$|[;:.,)\]]|\n))")


def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _li_depth(li: Tag) -> int:
    # количество родительских <li> = уровень вложенности
    d = 0
    p = li.parent
    while p is not None:
        if isinstance(p, Tag) and p.name == "li":
            d += 1
        p = p.parent
    return d


def _li_own_text(li: Tag) -> str:
    """
    Текст пункта <li> без текста вложенных списков <ol>/<ul>.
    Иначе подпункты будут вклеены в родителя.
    """
    # клонируем li
    li_clone = BeautifulSoup(str(li), "lxml").find("li")
    if not li_clone:
        return _clean_ws(li.get_text(" ", strip=True))

    # удаляем вложенные списки из клона
    for nested in li_clone.find_all(["ol", "ul"]):
        nested.decompose()

    return _clean_ws(li_clone.get_text(" ", strip=True))


def remove_only_list_markers(text: str) -> str:
    """
    Remove only list markers like (1) (2) (3) when they are standalone markers,
    while keeping '(2) weeks', '(12) months', '(50%)', etc.
    """
    if not text:
        return text

    protected: list[str] = []

    def protect(m: re.Match) -> str:
        protected.append(m.group(0))
        return f"__P{len(protected) - 1}__"

    tmp = _UNIT_AFTER_PARENS_RE.sub(protect, text)
    tmp = _LIST_MARKER_PARENS_RE.sub("", tmp)

    for i, original in enumerate(protected):
        tmp = tmp.replace(f"__P{i}__", original)

    tmp = re.sub(r"[ \t]{2,}", " ", tmp)
    tmp = re.sub(r"\n[ \t]+", "\n", tmp)
    return tmp.strip()


def preprocess_medical_necessity(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")

    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()

    lines: list[str] = []

    # 1) Параграфы/заголовки вне списков (intro + notes blocks вне li)
    for p in soup.find_all(["p", "h3", "h4"]):
        if p.find_parent("li") is None:
            t = _clean_ws(p.get_text(" ", strip=True))
            if t:
                lines.append(t)

    # 2) Списки: берём ТОЛЬКО <li>, каждый один раз
    for li in soup.find_all("li"):
        text = _li_own_text(li)
        if not text:
            continue
        indent = "  " * _li_depth(li)
        lines.append(f"{indent}- {text}")

    # fallback если вдруг li вообще нет
    if not any(line.lstrip().startswith("- ") for line in lines):
        t = _clean_ws(soup.get_text("\n", strip=True))
        lines = [x.strip() for x in t.splitlines() if x.strip()]

    out = "\n".join(lines)

    # Удаляем только маркеры (1)(2)(3) где это именно нумерация
    out = remove_only_list_markers(out)

    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out
