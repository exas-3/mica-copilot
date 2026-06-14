-- MiCA Compliance Copilot — schema
-- Applied automatically on first container start (docker-entrypoint-initdb.d) and,
-- idempotently, by `python -m app.rag.ingest`. embedding dim (1024) must match EMBED_DIM.

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Vector store: one row per (chunked) regulation provision ──────────────────
CREATE TABLE IF NOT EXISTS reg_chunks (
    id          bigserial PRIMARY KEY,
    source      text        NOT NULL DEFAULT 'mica',
    article_ref text        NOT NULL DEFAULT '',
    title       text        NOT NULL DEFAULT '',
    chunk_text  text        NOT NULL,
    source_url  text        NOT NULL DEFAULT '',
    chunk_index int         NOT NULL DEFAULT 0,
    embedding   vector(1024),
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Cosine ANN index (HNSW). pgvector >= 0.5 (pgvector/pgvector:pg16 ships it).
CREATE INDEX IF NOT EXISTS reg_chunks_embedding_idx
    ON reg_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS reg_chunks_article_idx ON reg_chunks (article_ref);

-- Full-text column for the (stretch) hybrid retrieval path.
ALTER TABLE reg_chunks
    ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(title,'') || ' ' || chunk_text)) STORED;
CREATE INDEX IF NOT EXISTS reg_chunks_tsv_idx ON reg_chunks USING gin (tsv);

-- ── ESMA registers ───────────────────────────────────────────────────────────
-- The register tables (casps, emt_issuers, art_issuers, other_whitepapers,
-- non_compliant) are owned and (re)created by app/register/sync.py from the real
-- ESMA CSVs — see that module for the live schema. Not defined here.

-- ── News corpus: full-text articles, chunked + embedded (v2) ──────────────────
-- One row per chunk; an article (url_hash) yields several rows. Dedup is at the
-- article level (poller checks url_hash before inserting an article's chunks).
CREATE TABLE IF NOT EXISTS news_chunks (
    id           bigserial PRIMARY KEY,
    url          text        NOT NULL,
    url_hash     text        NOT NULL,
    title        text        NOT NULL DEFAULT '',
    source_name  text        NOT NULL DEFAULT '',
    published_at timestamptz,
    chunk_index  int         NOT NULL DEFAULT 0,
    chunk_text   text        NOT NULL,
    embedding    vector(1024),
    entities     text[]      NOT NULL DEFAULT '{}',
    topic        text,
    region       text,
    metadata     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    fetched_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS news_chunks_embedding_idx ON news_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS news_chunks_published_idx ON news_chunks (published_at DESC);
CREATE INDEX IF NOT EXISTS news_chunks_urlhash_idx   ON news_chunks (url_hash);
CREATE INDEX IF NOT EXISTS news_chunks_entities_idx  ON news_chunks USING gin (entities);

-- Per-feed polling state (conditional GET validators).
CREATE TABLE IF NOT EXISTS news_sources (
    name          text PRIMARY KEY,
    rss_url       text NOT NULL,
    source_type   text NOT NULL,            -- 'regulator' | 'press'
    country       text,
    etag          text,
    last_modified text,
    last_polled   timestamptz,
    last_success  timestamptz
);
