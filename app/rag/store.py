"""Vector-store operations over the `reg_chunks` pgvector table.

Embeddings are bound as text and cast with ``::vector`` so we never depend on a
particular numpy/psycopg adapter version — robust across environments.
"""
from __future__ import annotations

import json
from typing import Sequence

from app.db import get_conn
from app.rag.chunk import Chunk


def _vec_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"


def reset_chunks() -> None:
    with get_conn() as conn:
        conn.execute("TRUNCATE reg_chunks RESTART IDENTITY")
        conn.commit()


def upsert_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> int:
    assert len(chunks) == len(embeddings), "chunks/embeddings length mismatch"
    rows = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for ch, emb in zip(chunks, embeddings):
                cur.execute(
                    """
                    INSERT INTO reg_chunks
                        (source, article_ref, title, chunk_text, source_url, chunk_index, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb)
                    """,
                    (
                        ch.source,
                        ch.article_ref,
                        ch.title,
                        ch.chunk_text,
                        ch.source_url,
                        ch.chunk_index,
                        _vec_literal(emb),
                        json.dumps(ch.metadata),
                    ),
                )
                rows += 1
        conn.commit()
    return rows


def search(query_embedding: list[float], k: int) -> list[dict]:
    """Cosine-nearest chunks. score = 1 - cosine_distance, so higher is closer."""
    vec = _vec_literal(query_embedding)
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT article_ref, title, source, source_url, chunk_text,
                   metadata->>'doc_type' AS doc_type,
                   1 - (embedding <=> %s::vector) AS score
            FROM reg_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vec, vec, k),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _search_lexical(query_text: str, k: int) -> list[dict]:
    """Full-text (lexical) ranked chunks via the generated `tsv` column + GIN index.

    Complements the semantic search for exact-term queries (article names, defined
    terms like 'asset-referenced token', 'white paper', 'conflicts of interest').
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT article_ref, title, source, source_url, chunk_text,
                   metadata->>'doc_type' AS doc_type,
                   ts_rank(tsv, plainto_tsquery('english', %s)) AS score
            FROM reg_chunks
            WHERE tsv @@ plainto_tsquery('english', %s)
            ORDER BY score DESC
            LIMIT %s
            """,
            (query_text, query_text, k),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _rrf_key(r: dict) -> tuple[str, str]:
    return (r.get("article_ref") or "", (r.get("chunk_text") or "")[:64])


def search_hybrid(
    query_text: str, query_embedding: list[float], k: int, pool: int = 40, rrf_k: int = 60
) -> list[dict]:
    """Reciprocal-Rank Fusion of the cosine (semantic) and tsv (lexical) result lists.

    Each list contributes 1/(rrf_k + rank) to a chunk's score; the top-k by fused score
    are returned. If the lexical arm is empty (stopword-only query) this degrades to pure
    vector search.
    """
    vec_rows = search(query_embedding, pool)
    lex_rows = _search_lexical(query_text, pool)
    scores: dict[tuple[str, str], float] = {}
    keep: dict[tuple[str, str], dict] = {}
    for rows in (vec_rows, lex_rows):
        for rank, r in enumerate(rows):
            key = _rrf_key(r)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
            keep.setdefault(key, r)
    ranked = sorted(keep.values(), key=lambda r: scores[_rrf_key(r)], reverse=True)
    return ranked[:k]


def _doc_key(r: dict) -> str:
    """Identify a chunk's source document (URL before the #article anchor)."""
    return (r.get("source_url") or r.get("article_ref") or "").split("#")[0]


def select_diverse(pool: list[dict], k: int, reserve_base: int, max_per_doc: int) -> list[dict]:
    """Pick k chunks not dominated by one source. First reserve up to ``reserve_base`` slots
    for the highest-scoring *base-regulation* provisions — so the authoritative article
    surfaces even when its more-detailed RTS/guidelines outrank it (e.g. Art 61 vs the ESMA
    reverse-solicitation guideline) — then fill the rest with the best remaining chunks,
    capping any single source document to ``max_per_doc``."""
    out: list[dict] = []
    doc_count: dict[str, int] = {}
    base_refs: set[str] = set()
    for r in pool:
        if len(out) >= reserve_base:
            break
        if (r.get("doc_type") or "") != "regulation":
            continue
        ref = r.get("article_ref") or ""
        if ref in base_refs:
            continue
        base_refs.add(ref)
        out.append(r)
        doc_count[_doc_key(r)] = doc_count.get(_doc_key(r), 0) + 1
    for r in pool:
        if len(out) >= k:
            break
        if any(r is o for o in out):
            continue
        dk = _doc_key(r)
        if doc_count.get(dk, 0) >= max_per_doc:
            continue
        doc_count[dk] = doc_count.get(dk, 0) + 1
        out.append(r)
    return out[:k]


def count_chunks() -> int:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT count(*) FROM reg_chunks").fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0
