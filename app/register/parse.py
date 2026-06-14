"""Parsing helpers for the ESMA register CSVs (dates, pipe-arrays, service codes, keys)."""
from __future__ import annotations

import re

_DATE = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")
_ISO = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")
_LETTER = re.compile(r"^\s*([a-jA-J])[.\)]")


def parse_date(s: str | None) -> str | None:
    """Return an ISO date string, tolerating DD/MM/YYYY and MM/DD/YYYY contamination."""
    s = (s or "").strip()
    if not s:
        return None
    iso = _ISO.match(s)
    if iso:
        return _safe(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    m = _DATE.match(s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    if mo > 12 and d <= 12:  # unambiguous US-format contamination -> swap
        d, mo = mo, d
    return _safe(y, mo, d)


def _safe(y: int, mo: int, d: int) -> str | None:
    if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def split_pipe(s: str | None) -> list[str]:
    return [p.strip() for p in (s or "").split("|") if p.strip()]


def service_letters(raw: str | None) -> list[str]:
    """Normalise ESMA service-code strings (e.g. 'a. custody | b. operation…') to a–j letters."""
    out: list[str] = []
    for part in split_pipe(raw):
        m = _LETTER.match(part)
        if m:
            out.append(m.group(1).lower())
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def clean(s: str | None) -> str | None:
    s = (s or "").strip()
    return s or None
