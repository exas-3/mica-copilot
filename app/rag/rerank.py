"""Optional cross-encoder reranking over a candidate pool.

A bi-encoder (the embedder) is fast but coarse; a cross-encoder reads the query and
each candidate *together* and scores true relevance, so it reliably promotes the right
provision into the top-k even when the embedding ranks it ~10–25th.

Off by default (``RERANK=off``) so the stock pipeline stays offline + fast. ``RERANK=local``
uses a key-free fastembed cross-encoder; ``RERANK=voyage`` uses Voyage's reranker (needs a key).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


def _doc_text(c: dict) -> str:
    """What the reranker reads for a candidate — article identity + body, matching the
    contextual text the documents are embedded with."""
    head = " — ".join(p for p in (c.get("article_ref") or "", c.get("title") or "") if p)
    body = (c.get("chunk_text") or "").strip()
    return f"{head}\n{body}" if head else body


class _LocalReranker:
    def __init__(self, model: str) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name=model)

    def rerank(self, query: str, candidates: list[dict], k: int) -> list[dict]:
        scores = list(self._model.rerank(query, [_doc_text(c) for c in candidates]))
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        return [candidates[i] for i in order[:k]]


class _VoyageReranker:
    def __init__(self, api_key: str, model: str = "rerank-2") -> None:
        import voyageai

        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def rerank(self, query: str, candidates: list[dict], k: int) -> list[dict]:
        res = self._client.rerank(query, [_doc_text(c) for c in candidates], model=self._model, top_k=k)
        return [candidates[r.index] for r in res.results]


@lru_cache
def get_reranker():
    """Build the configured reranker once (model load is cached). None when RERANK=off."""
    s = get_settings()
    if s.rerank == "local":
        return _LocalReranker(s.rerank_model)
    if s.rerank == "voyage":
        if not s.voyage_api_key:
            raise RuntimeError("RERANK=voyage but VOYAGE_API_KEY is empty. Set the key or use RERANK=local|off.")
        return _VoyageReranker(s.voyage_api_key)
    return None


def rerank(query: str, candidates: list[dict], k: int) -> list[dict]:
    """Reorder `candidates` by cross-encoder relevance and keep the top `k`.
    Falls back to a plain top-k slice when reranking is off or the pool is empty."""
    if not candidates:
        return []
    r = get_reranker()
    return r.rerank(query, candidates, k) if r else candidates[:k]
