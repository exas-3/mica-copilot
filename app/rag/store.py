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


def count_chunks() -> int:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT count(*) FROM reg_chunks").fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0
