"""News poller: RSS → full-text fetch → MiCA triage → chunk + embed into news_chunks.

Free and key-light: RSS + article HTML are fetched over plain HTTP; embeddings are local;
only the (cheap) Haiku relevance triage uses the API. Incremental + idempotent — dedup is
by normalized-URL hash, conditional GET (etag/Last-Modified) skips unchanged feeds.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import feedparser
import trafilatura

from app.config import get_settings
from app.db import get_conn
from app.news import classify as classify_mod
from app.news.entities import extract_entities
from app.news.sources import USER_AGENT, sources_for
from app.news.store import article_exists, upsert_article
from app.rag.chunk import chunk_record
from app.rag.embed import get_embedder
from app.rag.ingest import SCHEMA_SQL, _exec_sql_file

_TAG = re.compile(r"<[^>]+>")
_TRACK = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|source$)", re.I)


def _normalize_url(u: str) -> str:
    try:
        p = urlparse(u)
    except Exception:
        return u
    keep = [kv for kv in (p.query.split("&") if p.query else []) if kv and not _TRACK.match(kv.split("=")[0])]
    path = p.path.rstrip("/") or p.path
    s = urlunparse((p.scheme, p.netloc, path, "", "&".join(keep), ""))
    return s.rstrip("/")


def _url_hash(u: str) -> str:
    return hashlib.sha1(_normalize_url(u).encode("utf-8")).hexdigest()


def _snippet(s: str, n: int = 240) -> str:
    clean = re.sub(r"\s+", " ", _TAG.sub(" ", s or "")).strip()
    return clean[: n - 1] + "…" if len(clean) > n else clean


def _published(entry) -> datetime | None:
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if not ts:
        return None
    try:
        return datetime(*ts[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _seed_sources() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            for s in sources_for():
                cur.execute(
                    """
                    INSERT INTO news_sources (name, rss_url, source_type, country)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (name) DO UPDATE SET rss_url = EXCLUDED.rss_url,
                        source_type = EXCLUDED.source_type, country = EXCLUDED.country
                    """,
                    (s["name"], s["rss_url"], s["type"], s.get("country")),
                )
        conn.commit()


def _validators(name: str) -> tuple[str | None, str | None]:
    with get_conn() as conn:
        row = conn.execute("SELECT etag, last_modified FROM news_sources WHERE name = %s", (name,)).fetchone()
        return (row[0], row[1]) if row else (None, None)


def _save_validators(name: str, etag: str | None, modified: str | None, ok: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE news_sources SET etag=%s, last_modified=%s, last_polled=now()"
            + (", last_success=now()" if ok else "") + " WHERE name=%s",
            (etag, modified, name),
        )
        conn.commit()


def _fetch_fulltext(url: str) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        return trafilatura.extract(downloaded, include_comments=False, include_tables=False, favor_recall=True)
    except Exception:
        return None


def _summarize(text: str, title: str) -> str:
    """Transformative summary for NEWS_STORE=summary mode (copyright-safer)."""
    s = get_settings()
    if not s.has_claude:
        return _snippet(text, 600)
    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    resp = client.messages.create(
        model=s.cheap_model, max_tokens=400,
        messages=[{"role": "user", "content":
                   f"Summarise this news article in 4-6 factual sentences capturing entities, dates, "
                   f"and regulatory significance. No preamble.\n\nTitle: {title}\n\n{text[:6000]}"}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def poll(types: list[str] | None = None) -> dict:
    s = get_settings()
    _exec_sql_file(SCHEMA_SQL)
    _seed_sources()
    embedder = get_embedder()

    # 1) Collect new candidates across the selected feeds (conditional GET + dedup).
    candidates: list[dict] = []
    feeds_polled = 0
    for src in sources_for(types):
        etag, modified = _validators(src["name"])
        try:
            d = feedparser.parse(src["rss_url"], etag=etag, modified=modified, agent=USER_AGENT)
        except Exception:
            _save_validators(src["name"], etag, modified, ok=False)
            continue
        feeds_polled += 1
        if getattr(d, "status", None) == 304:
            _save_validators(src["name"], etag, modified, ok=True)
            continue
        headers = getattr(d, "headers", {}) or {}
        for entry in (d.entries or [])[: s.news_max_articles_per_feed]:
            url = entry.get("link") or entry.get("id")
            title = (entry.get("title") or "").strip()
            if not url or not title:
                continue
            uh = _url_hash(url)
            if article_exists(uh):
                continue
            candidates.append({
                "url": url, "url_hash": uh, "title": title,
                "summary": _snippet(entry.get("summary") or entry.get("description") or ""),
                "published_at": _published(entry), "source_name": src["name"],
                "source_type": src["type"],
            })
        _save_validators(src["name"], headers.get("etag") or etag, headers.get("last-modified") or modified, ok=True)

    if not candidates:
        return {"feeds_polled": feeds_polled, "candidates": 0, "ingested": 0}

    # 2) Triage relevance (Haiku, batched) — keep crypto-regulatory items.
    verdicts = classify_mod.classify_batch(candidates)
    relevant = [(c, v) for c, v in zip(candidates, verdicts) if v.get("relevant")]

    # 3) Full-text fetch → chunk → embed → upsert.
    ingested = 0
    for c, v in relevant:
        text = _fetch_fulltext(c["url"])
        if not text or len(text) < 200:
            continue
        if s.news_store == "summary":
            text = _summarize(text, c["title"])
        entities = extract_entities(f"{c['title']} {text}")
        chunks = chunk_record({"source": "news", "chunk_text": text, "title": c["title"], "source_url": c["url"]})
        chunk_texts = [ch.chunk_text for ch in chunks]
        if not chunk_texts:
            continue
        embeddings = embedder.embed_documents(chunk_texts)
        meta = {"url": c["url"], "url_hash": c["url_hash"], "title": c["title"],
                "source_name": c["source_name"], "published_at": c["published_at"],
                "metadata": {"method": v.get("method")}}
        upsert_article(meta, chunk_texts, embeddings, entities, v.get("topic"), v.get("region"))
        ingested += 1

    return {"feeds_polled": feeds_polled, "candidates": len(candidates),
            "relevant": len(relevant), "ingested": ingested}
