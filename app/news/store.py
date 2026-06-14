"""Vector-store operations over `news_chunks` with recency-weighted retrieval."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Sequence

from app.db import get_conn
from app.rag.store import _vec_literal  # shared "[...]"::vector literal helper


def article_exists(url_hash: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM news_chunks WHERE url_hash = %s LIMIT 1", (url_hash,)).fetchone()
        return row is not None


def upsert_article(meta: dict, chunk_texts: list[str], embeddings: list[list[float]],
                   entities: list[str], topic: str | None, region: str | None) -> int:
    rows = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for idx, (text, emb) in enumerate(zip(chunk_texts, embeddings)):
                cur.execute(
                    """
                    INSERT INTO news_chunks
                        (url, url_hash, title, source_name, published_at, chunk_index,
                         chunk_text, embedding, entities, topic, region, metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,%s,%s,%s::jsonb)
                    """,
                    (
                        meta["url"], meta["url_hash"], meta.get("title", ""),
                        meta.get("source_name", ""), meta.get("published_at"), idx,
                        text, _vec_literal(emb), entities, topic, region,
                        json.dumps(meta.get("metadata", {})),
                    ),
                )
                rows += 1
        conn.commit()
    return rows


def search_news(query_embedding: list[float], k: int, halflife_days: float,
                entity: str | None = None) -> list[dict]:
    """Blended score = 0.7·cosine_sim + 0.3·recency_decay + 0.25·entity_match."""
    vec = _vec_literal(query_embedding)
    ent = (entity or "").strip()
    with get_conn() as conn:
        cur = conn.execute(
            f"""
            SELECT url, url_hash, title, source_name, published_at, chunk_text, entities, topic,
                   (1 - (embedding <=> %s::vector)) AS sim
            FROM news_chunks
            ORDER BY
                0.7 * (1 - (embedding <=> %s::vector))
              + 0.3 * (CASE WHEN published_at IS NULL THEN 0.4
                            ELSE exp(-0.6931 * GREATEST(0, extract(epoch FROM (now() - published_at)) / 86400.0) / %s)
                       END)
              + (CASE WHEN %s <> '' AND entities @> ARRAY[%s] THEN 0.25 ELSE 0 END) DESC
            LIMIT %s
            """,
            (vec, vec, halflife_days, ent, ent, k),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def count_articles() -> int:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT count(DISTINCT url_hash) FROM news_chunks").fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def reset_news() -> None:
    with get_conn() as conn:
        conn.execute("TRUNCATE news_chunks")
        conn.commit()
