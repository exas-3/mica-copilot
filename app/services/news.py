"""News retrieval for the agent's `search_news` tool: embed → recency-weighted search →
dated context block + citations."""
from __future__ import annotations

from app.config import get_settings
from app.news.store import search_news
from app.rag.embed import get_embedder


def retrieve_news(query: str, entity: str | None = None) -> list[dict]:
    s = get_settings()
    vec = get_embedder().embed_query(query)
    return search_news(vec, s.news_return_k, s.news_recency_halflife_days, entity)


def _date(row: dict) -> str:
    d = row.get("published_at")
    try:
        return d.strftime("%Y-%m-%d") if d else "undated"
    except Exception:
        return "undated"


def build_news_context(rows: list[dict]) -> str:
    if not rows:
        return "(no relevant news articles were retrieved)"
    blocks = []
    for i, r in enumerate(rows, 1):
        head = f"[N{i}] {r.get('source_name', '')} · {_date(r)} — {r.get('title', '')}"
        blocks.append(f"{head}\n{(r.get('chunk_text', '') or '').strip()}")
    return "\n\n".join(blocks)


def to_news_citations(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        url = r.get("url") or ""
        if url in seen:
            continue
        seen.add(url)
        text = (r.get("chunk_text") or "").strip().replace("\n", " ")
        out.append({
            "kind": "news",
            "article_ref": "",
            "title": r.get("title") or "",
            "source": "news",
            "source_name": r.get("source_name") or "",
            "published_at": _date(r) if r.get("published_at") else "",
            "source_url": url,
            "snippet": (text[:200] + "…") if len(text) > 200 else text,
        })
    return out
