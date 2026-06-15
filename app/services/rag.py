"""Retrieval-augmented generation helpers.

retrieve() -> nearest regulation chunks; build_context() -> a numbered, citable
context block for the prompt; to_citations() -> deduped citation records for the UI.
"""
from __future__ import annotations

from app.config import get_settings
from app.rag.embed import get_embedder
from app.rag.store import search, search_hybrid, select_diverse


def retrieve(query: str, k: int | None = None) -> list[dict]:
    s = get_settings()
    embedder = get_embedder()
    vec = embedder.embed_query(query)
    rows = search(vec, k or s.top_k)
    return rows[: (k or s.return_k)] if k is None else rows


def retrieve_for_answer(query: str) -> list[dict]:
    """Retrieve the best RETURN_K chunks for the model.

    Pipeline: embed the query (with the model's query prompt) → candidate search
    (hybrid vector+lexical RRF, or pure vector) over a pool → optional cross-encoder
    rerank → keep RETURN_K. Reranking is off by default (keeps the default offline + fast).
    """
    s = get_settings()
    vec = get_embedder().embed_query(query)

    # Reranker path (opt-in, off by default): rerank a larger candidate pool down to return_k.
    if s.rerank != "off":
        pool_n = max(s.top_k, s.rerank_pool)
        rows = search_hybrid(query, vec, pool_n) if s.retrieval_mode == "hybrid" else search(vec, pool_n)
        from app.rag.rerank import rerank as _rerank

        return _rerank(query, rows, s.return_k)

    # Diversity path (default): fetch a large pool, then reserve base-regulation slots and cap
    # per source document so an article isn't crowded out by its own RTS/guidelines.
    if s.retrieval_mode == "hybrid" and s.retrieval_diversity:
        pool = search_hybrid(query, vec, s.diversity_pool, pool=s.diversity_pool)
        return select_diverse(pool, s.return_k, s.reserve_base, s.max_per_doc)

    # Plain top-k.
    rows = search_hybrid(query, vec, s.top_k) if s.retrieval_mode == "hybrid" else search(vec, s.top_k)
    return rows[: s.return_k]


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "(no matching provisions were retrieved)"
    blocks = []
    for i, c in enumerate(chunks, 1):
        ref = c.get("article_ref") or "Unknown provision"
        title = c.get("title") or ""
        head = f"[{i}] {ref}" + (f" — {title}" if title else "")
        blocks.append(f"{head}\n{c.get('chunk_text', '').strip()}")
    return "\n\n".join(blocks)


def to_citations(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for c in chunks:
        ref = c.get("article_ref") or ""
        if ref in seen:
            continue
        seen.add(ref)
        text = (c.get("chunk_text") or "").strip().replace("\n", " ")
        out.append(
            {
                "kind": "document",
                "article_ref": ref,
                "title": c.get("title") or "",
                "source": c.get("source") or "mica",
                "doc_type": c.get("doc_type") or "",
                "source_url": c.get("source_url") or "",
                "snippet": (text[:220] + "…") if len(text) > 220 else text,
            }
        )
    return out
