"""EUR-Lex fetch + article-aware parsing for any MiCA CELEX document.

Handles the base Regulation (32023R1114) and the Level-2 Delegated/Implementing
Regulations (RTS/ITS). Articles are split on "Article N" headings; each becomes a
citable record with a stable EUR-Lex deep link. Best-effort: if no articles parse
(unusual layout), the whole text is returned as one record for window-chunking.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

REG_CELEX = "32023R1114"
ELI = "https://eur-lex.europa.eu/eli/reg/2023/1114/oj"
_TAG = re.compile(r"<[^>]+>")
_ART_SPLIT = re.compile(r"(?m)^\s*Article\s+(\d+)\s*$")
_UA = {"User-Agent": "MiCA-Copilot/0.2 (+educational; non-commercial)"}


def html_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"


def txt_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def short_label(celex: str, doc_type: str) -> str:
    if celex == REG_CELEX:
        return "MiCA"
    m = re.match(r"3(\d{4})R(\d+)", celex or "")
    if m:
        kind = "IR" if doc_type == "its" else "DR"
        return f"{kind} {m.group(1)}/{int(m.group(2))}"
    return (doc_type or "doc").upper()


def _detag(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)</p>|</div>|<br\s*/?>", "\n", html)
    text = _TAG.sub(" ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text)


def parse_articles(html: str, celex: str, title: str, doc_type: str) -> list[dict]:
    text = _detag(html)
    parts = _ART_SPLIT.split(text)
    label = short_label(celex, doc_type)
    anchor_base = ELI if celex == REG_CELEX else txt_url(celex)
    records: list[dict] = []
    for i in range(1, len(parts) - 1, 2):
        num = parts[i].strip()
        body = parts[i + 1].strip()
        if len(body) < 40:
            continue
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        art_title = lines[0] if lines else ""
        art_body = "\n".join(lines[1:]) if len(lines) > 1 else body
        ref = f"Article {num}" if celex == REG_CELEX else f"{label} Art. {num}"
        records.append({
            "source": "document",
            "article_ref": ref,
            "title": (art_title[:200] if celex == REG_CELEX else f"{art_title[:120]} — {title[:90]}"),
            # generous per-article cap: long articles (e.g. Art 3 definitions) are split into
            # sub-budget chunks downstream, so we keep the full text instead of truncating it.
            "chunk_text": art_body[:16000],
            "source_url": f"{anchor_base}#art_{num}",
            "metadata": {"celex": celex, "doc_type": doc_type, "label": label},
        })
    return records


_DEF_QUOTE = "'‘’\"“”"
_DEF_START = re.compile(rf"\(\d{{1,3}}\)\s*[{_DEF_QUOTE}]")
_DEF_SPLIT = re.compile(rf"(?=\(\d{{1,3}}\)\s*[{_DEF_QUOTE}])")
_DEF_HEAD = re.compile(rf"\((\d{{1,3}})\)\s*[{_DEF_QUOTE}]([^{_DEF_QUOTE}]+)[{_DEF_QUOTE}]")


def _split_definitions(body: str, celex: str, doc_type: str) -> list[dict]:
    """Turn the Article 3 'Definitions' list into one record per defined term, so a single
    term (e.g. 'asset-referenced token') is retrievable on its own instead of diluted in one
    big blob. Returns [] if fewer than 10 terms parse (caller then keeps the whole article)."""
    text = re.sub(r"[ \t]+", " ", (body or "").replace("\n", " ")).strip()
    pieces = [p.strip() for p in _DEF_SPLIT.split(text) if _DEF_START.match(p.strip())]
    if len(pieces) < 10:
        return []
    recs: list[dict] = []
    for p in pieces:
        m = _DEF_HEAD.match(p)
        if not m:
            continue
        num, term = m.group(1), m.group(2).strip()
        recs.append({
            "source": "document",
            "article_ref": f"Article 3({num})",
            "title": f"Definition: {term}"[:200],
            "chunk_text": p[:1800].rstrip("; "),
            "source_url": f"{ELI}#art_3",
            "metadata": {"celex": celex, "doc_type": doc_type, "label": "MiCA", "def_term": term},
        })
    return recs


def expand_art3_definitions(records: list[dict]) -> list[dict]:
    """Replace the single Article 3 record with per-definition records (called at ingest)."""
    out: list[dict] = []
    for r in records:
        meta = r.get("metadata") or {}
        if r.get("article_ref") == "Article 3" and meta.get("celex") == REG_CELEX:
            defs = _split_definitions(r.get("chunk_text") or "", REG_CELEX, meta.get("doc_type", "regulation"))
            if defs:
                out.extend(defs)
                continue
        out.append(r)
    return out


def fetch_celex_records(celex: str, title: str, doc_type: str) -> list[dict]:
    try:
        resp = httpx.get(html_url(celex), timeout=60, follow_redirects=True, headers=_UA)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"   ! EUR-Lex fetch failed for {celex}: {e}")
        return []
    records = parse_articles(resp.text, celex, title, doc_type)
    if records:
        return records
    # Fallback: whole document as one record (docs_ingest will window-chunk it).
    body = _detag(resp.text)
    if len(body) < 200:
        return []
    return [{
        "source": "document", "article_ref": short_label(celex, doc_type),
        "title": title[:200], "chunk_text": body[:200000], "source_url": txt_url(celex),
        "metadata": {"celex": celex, "doc_type": doc_type, "label": short_label(celex, doc_type)},
    }]


def refresh_corpus(out_path: Path) -> None:
    """Back-compat: rebuild the base-regulation summary corpus (used by `ingest --refresh`)."""
    records = fetch_celex_records(REG_CELEX, "Regulation (EU) 2023/1114 (MiCA)", "regulation")
    if len(records) < 50:
        print(f"   ! Parsed only {len(records)} articles — keeping existing corpus.")
        return
    out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    print(f"   wrote {len(records)} articles to {out_path.name}")
