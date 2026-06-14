"""Read-only lookups against the real ESMA registers (synced by app/register/sync.py).

Covers CASP authorisations, EMT/ART issuers, **Title II crypto-asset white papers**
(searched by the token name/ticker read from the white-paper document, plus offeror and
URL), and non-compliant warnings. Every query degrades to [] if a table is missing.
"""
from __future__ import annotations

from app.db import get_conn


def _safe(query: str, params: tuple) -> list[tuple]:
    try:
        with get_conn() as conn:
            return conn.execute(query, params).fetchall()
    except Exception:
        return []


def search_registry(query: str, limit: int = 20) -> list[dict]:
    like = f"%{query.strip()}%"
    out: list[dict] = []

    for r in _safe(
        "SELECT commercial_name, lei_name, country, lei FROM casps "
        "WHERE commercial_name ILIKE %s OR lei_name ILIKE %s ORDER BY commercial_name LIMIT %s",
        (like, like, limit),
    ):
        out.append({"kind": "casp", "name": r[0] or r[1], "country": r[2], "source_url": None,
                    "detail": "Authorised crypto-asset service provider (ESMA register)"})

    for tbl, label in (("emt_issuers", "Authorised e-money token issuer"),
                       ("art_issuers", "Authorised asset-referenced token issuer")):
        for r in _safe(
            f"SELECT commercial_name, lei_name, country, wp_url FROM {tbl} "
            "WHERE commercial_name ILIKE %s OR lei_name ILIKE %s ORDER BY commercial_name LIMIT %s",
            (like, like, limit),
        ):
            out.append({"kind": tbl[:-1], "name": r[0] or r[1], "country": r[2], "source_url": r[3],
                        "detail": f"{label} (ESMA register)"})

    # Title II crypto-asset white papers — match the token read from the document, offeror, or URL.
    for r in _safe(
        "SELECT token_name, ticker, lei_name, lei_name_casp, country, wp_url, extract_confidence "
        "FROM other_whitepapers "
        "WHERE token_name ILIKE %s OR ticker ILIKE %s OR lei_name ILIKE %s "
        "      OR lei_name_casp ILIKE %s OR wp_url ILIKE %s "
        "ORDER BY (token_name IS NULL), token_name LIMIT %s",
        (like, like, like, like, like, limit),
    ):
        token, ticker, offeror = r[0], r[1], (r[2] or r[3])
        name = token or ticker or offeror or "(unnamed white paper)"
        conf = " (token read from the white paper; lower confidence)" if r[6] in ("low", "none") else ""
        out.append({"kind": "whitepaper", "name": name + (f" ({ticker})" if ticker and ticker != name else ""),
                    "country": r[4], "source_url": r[5],
                    "detail": f"Title II crypto-asset white paper — offeror: {offeror or 'n/a'}{conf}"})

    for r in _safe(
        "SELECT commercial_name, lei_name, competent_authority, reason FROM non_compliant "
        "WHERE commercial_name ILIKE %s OR lei_name ILIKE %s ORDER BY commercial_name LIMIT %s",
        (like, like, limit),
    ):
        out.append({"kind": "non_compliant", "name": r[0] or r[1], "country": None, "source_url": None,
                    "detail": f"Flagged by {r[2]}" + (f": {r[3]}" if r[3] and r[3] != "None" else "")})

    return out[: limit + 10]


def check_enforcement(entity: str, limit: int = 15) -> list[dict]:
    like = f"%{entity.strip()}%"
    rows = _safe(
        "SELECT commercial_name, lei_name, competent_authority, reason, decision_date FROM non_compliant "
        "WHERE commercial_name ILIKE %s OR lei_name ILIKE %s ORDER BY decision_date DESC NULLS LAST LIMIT %s",
        (like, like, limit),
    )
    return [{"entity": r[0] or r[1], "authority": r[2], "reason": r[3],
             "decision_date": str(r[4]) if r[4] else None} for r in rows]


def register_row_count() -> int:
    total = 0
    for table in ("casps", "emt_issuers", "art_issuers", "other_whitepapers", "non_compliant"):
        rows = _safe(f"SELECT count(*) FROM {table}", ())
        if rows:
            total += int(rows[0][0])
    return total
