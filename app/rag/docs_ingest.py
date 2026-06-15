"""Build the official document corpus into `reg_chunks`.

Sources (data/document_sources.json): EUR-Lex regulation + Level-2 RTS/ITS (CELEX) and
ESMA/EBA guidelines & Q&As (PDF/HTML). Each is fetched, text-extracted, article/section
chunked, embedded, and upserted — replacing the hand-written summaries with authoritative,
citable text. Extracted records are cached to data/document_corpus.jsonl for offline rebuilds.

    python -m app.rag.docs_ingest            # use cache if present, else fetch
    python -m app.rag.docs_ingest --refresh  # re-fetch all sources
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import close_pool
from app.rag import eurlex
from app.rag.chunk import chunk_record
from app.rag.embed import get_embedder
from app.rag.ingest import SCHEMA_SQL, _exec_sql_file
from app.rag.pdf import extract_text
from app.rag.store import reset_chunks, upsert_chunks

ROOT = Path(__file__).resolve().parents[2]
FALLBACK_CORPUS = ROOT / "data" / "corpus.jsonl"
_UA = {"User-Agent": "MiCA-Copilot/0.2 (+educational; non-commercial)"}


def _fetch_pdf_or_html(src: dict) -> list[dict]:
    url = src["url"]
    try:
        resp = httpx.get(url, timeout=90, follow_redirects=True, headers=_UA)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"   ! fetch failed: {src['title'][:60]} ({e})")
        return []
    text = extract_text(resp.content, resp.headers.get("content-type", ""), url)
    if not text or len(text) < 200:
        print(f"   ! no extractable text: {src['title'][:60]}")
        return []
    auth = src.get("authority", "")
    return [{
        "source": "document",
        "article_ref": f"{auth} {src.get('doc_type','doc')}: {src['title'][:48]}".strip(),
        "title": src["title"][:240],
        "chunk_text": text[:400000],
        "source_url": url,
        "metadata": {"doc_type": src.get("doc_type"), "authority": auth},
    }]


def build_records() -> list[dict]:
    s = get_settings()
    sources = json.loads((ROOT / s.document_sources_path).read_text(encoding="utf-8"))
    records: list[dict] = []
    for i, src in enumerate(sources, 1):
        label = src.get("celex") or src.get("title", "")[:50]
        print(f"  [{i}/{len(sources)}] {src['doc_type']:11} {label}")
        if src["kind"] == "eurlex":
            recs = eurlex.fetch_celex_records(src["celex"], src["title"], src["doc_type"])
        else:
            recs = _fetch_pdf_or_html(src)
        records.extend(recs)
    return records


def _load_or_build(refresh: bool) -> list[dict]:
    s = get_settings()
    cache = ROOT / s.document_corpus_path
    if cache.exists() and not refresh:
        print(f"→ Using cached document corpus ({cache.name})")
        return [json.loads(l) for l in cache.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("→ Fetching documents from EUR-Lex / ESMA / EBA…")
    records = build_records()
    if records:
        cache.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
        print(f"   cached {len(records)} records → {cache.name}")
    elif FALLBACK_CORPUS.exists():
        print("   ! no documents fetched — falling back to data/corpus.jsonl (summaries)")
        records = [json.loads(l) for l in FALLBACK_CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the official MiCA document corpus.")
    ap.add_argument("--refresh", action="store_true", help="Re-fetch all sources (ignore cache).")
    args = ap.parse_args()

    s = get_settings()
    print(f"→ Embedder: {s.embedder}, dim={s.embed_dim}")
    _exec_sql_file(SCHEMA_SQL)

    records = _load_or_build(args.refresh)
    if not records:
        raise SystemExit("No document records to ingest. Check network or data/document_sources.json.")

    records = eurlex.expand_art3_definitions(records)  # Art 3 → one record per defined term
    chunks = [c for r in records for c in chunk_record(r)]
    print(f"→ {len(records)} documents/articles → {len(chunks)} chunks; embedding…")
    embeddings = get_embedder().embed_documents([c.chunk_text for c in chunks])

    reset_chunks()
    n = upsert_chunks(chunks, embeddings)
    print(f"   indexed {n} chunks into reg_chunks")

    print("→ Loading ESMA registers (real CSV snapshot)…")
    try:
        from app.register import sync as register_sync
        print("   registers:", register_sync.load(refresh=False))
    except Exception as e:  # noqa: BLE001
        print(f"   ! register load skipped: {e}")
    print("✓ Document corpus ready.")
    close_pool()


if __name__ == "__main__":
    main()
