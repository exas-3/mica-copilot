"""Build the knowledge base: schema → embed corpus → seed register snapshot.

Usage:
    python -m app.rag.ingest                # build from data/corpus.jsonl (offline, default)
    python -m app.rag.ingest --refresh      # first pull fresh MiCA text from EUR-Lex, then build

It is idempotent: it (re)applies the schema, truncates and rebuilds `reg_chunks`, and
reloads the register snapshot. Safe to run against the docker Postgres or any Postgres
with pgvector available.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.db import close_pool, get_conn
from app.rag.chunk import chunk_record
from app.rag.embed import get_embedder
from app.rag.store import reset_chunks, upsert_chunks

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "corpus.jsonl"
SCHEMA_SQL = ROOT / "db" / "0001_init.sql"


def _exec_sql_file(path: Path) -> int:
    """Run every statement in a .sql file.

    Comments are stripped *before* splitting on ';' so that (a) a statement preceded by a
    comment isn't dropped and (b) a ';' inside a comment isn't mistaken for a statement
    boundary. These schema/seed files contain no '--' or ';' inside string literals.
    """
    if not path.exists():
        return 0
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)  # block comments
    cleaned = "\n".join(re.sub(r"--.*$", "", line) for line in raw.splitlines())  # line/inline comments
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    with get_conn() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
    return len(statements)


def _load_corpus() -> list[dict]:
    if not CORPUS.exists():
        sys.exit(f"Corpus not found at {CORPUS}. Commit data/corpus.jsonl or run with --refresh.")
    records = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MiCA copilot knowledge base.")
    parser.add_argument("--refresh", action="store_true", help="Pull fresh MiCA text from EUR-Lex first (best effort).")
    args = parser.parse_args()

    s = get_settings()
    print(f"→ Embedder: {s.embedder} ({s.voyage_model if s.embedder == 'voyage' else s.local_embed_model}), dim={s.embed_dim}")

    if args.refresh:
        from app.rag import eurlex

        print("→ Refreshing corpus from EUR-Lex (best effort)…")
        eurlex.refresh_corpus(CORPUS)

    print("→ Applying schema (db/0001_init.sql)…")
    _exec_sql_file(SCHEMA_SQL)

    print("→ Loading corpus + chunking…")
    records = _load_corpus()
    chunks = [c for r in records for c in chunk_record(r)]
    print(f"   {len(records)} provisions → {len(chunks)} chunks")

    print("→ Embedding…")
    embedder = get_embedder()
    texts = [c.chunk_text for c in chunks]
    embeddings = embedder.embed_documents(texts)

    print("→ Upserting into reg_chunks…")
    reset_chunks()
    n = upsert_chunks(chunks, embeddings)
    print(f"   indexed {n} chunks")

    print("→ Loading ESMA registers…")
    try:
        from app.register import sync as register_sync
        print("   registers:", register_sync.load(refresh=False))
    except Exception as e:  # noqa: BLE001
        print(f"   ! register load skipped: {e}")

    print("✓ Knowledge base ready.")
    close_pool()


if __name__ == "__main__":
    main()
