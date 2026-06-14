# Methodology

How the MiCA Compliance Copilot turns the [data sources](DATA-SOURCES.md) into grounded, cited answers —
the ingestion, chunking, embedding, retrieval, agent routing, grounding, structured-output and evaluation
methods, with the exact parameters used.

```
                  ┌──────────────┐   ┌──────────┐   ┌────────────┐   ┌─────────────────┐
  public sources →│   ingest     │ → │  chunk   │ → │   embed    │ → │  pgvector store │
  (docs/news/reg) │ fetch+parse  │   │ 1800 ch  │   │ 1024-dim   │   │ reg_chunks /    │
                  └──────────────┘   └──────────┘   └────────────┘   │ news_chunks +   │
                                                                     │ register tables │
                                                                     └────────┬────────┘
  user question ─► FastAPI ─► Claude agent loop ──tools──► retrieve (cosine / blended) ──┘
                              (Sonnet 4.6)        search_regulation · search_news ·
                              grounded + cited    lookup_register · check_enforcement
```

---

## 1. Ingestion

Three independent, idempotent pipelines, each cached in `data/` so the whole system **rebuilds offline**.

- **Documents** (`app/rag/docs_ingest.py`) — fetch the 34 sources (EUR-Lex by CELEX → article-parsed;
  ESMA/EBA → PDF/HTML text), cache to `document_corpus.jsonl`, then chunk → embed → **truncate &
  re-upsert** `reg_chunks`.
- **News** (`app/news/poller.py`) — conditional-GET each feed → dedup by URL hash → **MiCA-relevance
  triage** (Haiku, batches of 20: keeps only crypto-asset items in a *regulatory* context, tags
  `region` + `topic`) → full-text fetch (`trafilatura`) → deterministic **entity tagging** (≈40 firms +
  ≈12 stablecoin tickers) → chunk → embed → upsert `news_chunks`. Offline, a keyword heuristic replaces
  the Haiku triage.
- **Registers** (`app/register/sync.py`) — fetch 5 ESMA CSVs → normalise (dates, `a`–`j` service codes,
  dedup by primary key) → snapshot to JSON → load tables; then **white-paper token reads** layer
  `token_name`/`ticker` onto `other_whitepapers` (see [DATA-SOURCES § 4](DATA-SOURCES.md#4-white-paper-token-reads--other_whitepaperstoken_name--ticker)).

## 2. Chunking

`app/rag/chunk.py` — a single article/section becomes one or more chunks under a **1 800-character soft
budget**, packed greedily on **paragraph boundaries** (`\n\n`); paragraphs are never split mid-way. A
record under the budget stays whole. Every chunk inherits its parent's `article_ref`, `title`,
`source_url` and `metadata` (so citation survives chunking). Both corpora use the same chunker.

## 3. Embeddings

`app/rag/embed.py` — one `Embedder` interface, two interchangeable backends, **both 1024-dimensional**:

| Backend | Model | Notes |
|---|---|---|
| **local** (default) | `mixedbread-ai/mxbai-embed-large-v1` via `fastembed` | ~0.64 GB, fully **offline, no API key** → reproducible for a grader |
| voyage | `voyage-law-2` | legal/long-context tuned; needs `VOYAGE_API_KEY`; batches 128; distinguishes `document` vs `query` input type |

The pgvector schema is identical either way, so swapping backends only requires re-embedding.

## 4. Vector store & indexes

PostgreSQL + **pgvector** (`db/0001_init.sql`). Vectors are bound as `::vector` text literals (no
numpy/psycopg adapter dependency).

- **`reg_chunks`** — `article_ref`, `title`, `chunk_text`, `source_url`, `embedding vector(1024)`,
  `metadata` (incl. `doc_type`, `celex`). Indexes: **HNSW `vector_cosine_ops`** on the embedding, a B-tree
  on `article_ref`, and a **GIN `tsvector`** index (`tsv`) reserved for a future hybrid BM25+vector path
  (not yet used at query time).
- **`news_chunks`** — adds `published_at`, `entities[]`, `topic`, `region`. Indexes: **HNSW cosine** on
  the embedding, B-tree on `published_at DESC`, **GIN on `entities`** for entity filtering.

## 5. Retrieval

**Regulation** (`app/services/rag.py`): embed the query → cosine ANN search (`<=>`) over `reg_chunks`,
pull **`top_k = 20`** candidates, hand the **`return_k = 6`** best to the model. Score = `1 − cosine_distance`.

**News** (`app/news/store.py`): a **blended score**, not pure similarity —

```
score = 0.7 · cosine_similarity
      + 0.3 · recency_decay        # exp(−ln2 · days_old / 21);  null date → 0.4
      + 0.25 · entity_match        # +0.25 if the queried entity is in the chunk's entities[]
```

so a slightly-less-similar but **fresher** item about the **named entity** can outrank a stale exact match
(`news_return_k = 6`, half-life `21 days`).

**Context & citations.** Retrieved chunks are formatted as a numbered block — `[i] {article_ref} —
{title}\n{chunk_text}` — and given to the model. Citations are de-duplicated: **by `article_ref`** for
documents, **by `source_url`** for news (each with a ~200-char snippet, `doc_type`, and date for news).

## 6. The agent & tool routing

`app/services/llm.py` runs a **manual agentic loop** (`claude-sonnet-4-6`; adaptive thinking, `effort:
medium`; up to **5 tool iterations**; `max_tokens` 4096 chat / 2048 classify). The model chooses among
four tools, each with a prescriptive *when-to-call* description (`app/agents/tools.py`):

| Tool | Call it for | Reads |
|---|---|---|
| `search_regulation` | what the **law requires** — rules, definitions, thresholds, obligations | `reg_chunks` |
| `search_news` | **current status** / recent developments / deadlines / "what's happening with X" | `news_chunks` (dated) |
| `lookup_register` | is a firm/token **authorised / registered**, or does it have a white paper | ESMA register tables |
| `check_enforcement` | **warnings / enforcement** against a named entity | `non_compliant` |

The system prompt (`app/agents/prompts.py`) ships a stable **MiCA "map"** (Titles I–VIII, article ranges,
the `a`–`j` services, classification heuristics) plus explicit **routing rules** (law → `search_regulation`;
current facts → `search_news` + register; "does *token* have a white paper" → `lookup_register`, noting
coverage is not exhaustive). The SSE stream surfaces the loop as `tool` / `token` / `reset` / `thought` /
`citations` / `done` events.

## 7. Grounding & abstention

The core rule, verbatim from the system prompt:

> You answer **ONLY** from regulation provisions retrieved via your tools — never from unverified memory.
> Before answering any substantive MiCA question you MUST call `search_regulation`. … If the retrieved
> provisions do not actually support an answer, **say so explicitly** ("The indexed MiCA corpus doesn't
> contain a provision answering this — I can't answer reliably.") and do **NOT** fall back to general
> knowledge. Partial coverage → answer what is supported and flag the gap.

Operationally, the response's **`grounded` flag is `bool(citations)`** — no retrieved sources → not
grounded → the UI shows a *"No grounding — answer withheld"* badge. In a compliance setting, a
confident-but-wrong answer is worse than "I don't know," so abstention is a feature, not a failure mode.

## 8. Structured classification

`/classify` constrains Claude's output to a JSON schema via `output_config = {format: {type:
"json_schema", schema: …}}` (`additionalProperties: false`). Fields: `asset_type` (enum: *ART / EMT /
other crypto-asset / out of scope / uncertain*), `asset_rationale`, `services[]` (the `a`–`j` letters with
`applies`), `obligations[]` (each with an `article_ref`), `citations[]`, and `confidence` (low/medium/high).
Model-returned citations are **merged with the RAG grounding citations** so the UI always has working
source links; an older SDK without `output_config` falls back to an in-prompt JSON request + tolerant
parse.

## 9. Prompt caching

The large, stable system prefix (MiCA map + rules) carries `cache_control: {type: "ephemeral"}`, and
**per-question context is appended *after* it** (never inside the cached block) — so repeat requests pay
cache-read (~0.1×) instead of full price. Verified: a second call read ~1,693 `cache_read_input_tokens`.

## 10. Evaluation methodology

`python -m eval.run [--e2e] [--judge]` against **`eval/goldens.jsonl` — 13 hand-curated cases** (11
*answerable* with an expected article, 2 *abstain* / out-of-corpus). Three modes: retrieval-only (no key),
`--e2e` (full agent loop), `--e2e --judge` (adds the LLM judge).

| Metric | Definition | Measured |
|---|---|---|
| `retrieval_hit@k` | does an expected article appear in the `return_k = 6` retrieved chunks? | **0.727** |
| `citation_hit` | did the agent's answer actually **cite** an expected article? (`--e2e`) | **0.818** |
| `abstention_accuracy` | on out-of-corpus questions, did it abstain (`grounded=false` / no citations)? | **1.000** |
| `faithfulness` | LLM judge (`claude-haiku-4-5`, one-word *SUPPORTED/UNSUPPORTED*) over the retrieved context | **0.818** |

(Agent `claude-sonnet-4-6`, embedder local mxbai, v2 ~935-chunk corpus; per-question rows in
`eval/results/scorecard.json`.) The strict *exact-article* retrieval score is a little lower against the
richer Level-2 corpus because the expected article now competes with closely-related RTS provisions — the
answers are *richer* (they cite the RTS **and** the article) while abstention stays perfect.

**What the eval does *not* cover (by design, and honestly):** the `search_news`, `lookup_register` and
`check_enforcement` tools; the `/classify` endpoint; multi-turn chat; and latency/cost. The judge is a
single model with no human cross-check, and the golden set is small. These are the obvious next
extensions (a news/register golden set, a second judge).

## 11. Reproducibility & limitations

- **Reproducible offline.** Documents, registers and white-paper reads are cached in `data/`; the default
  embedder is local and key-free; retrieval-only eval needs no API key. Same corpus + snapshot → same scores.
- **Snapshots, not live feeds.** News reflects the last poll; registers reflect the last sync (ESMA's
  `2024-12` base). Keep them fresh with the [refresh commands](DATA-SOURCES.md#6-refresh-cadence).
- **Best-effort coverage.** Dead document/white-paper links are skipped; white-paper token coverage is
  partial (≈63 %); absence from the register is *not* proof of non-compliance.
- **Not legal advice.** General information about MiCA, grounded in public sources and cited.

See [`DATA-SOURCES.md`](DATA-SOURCES.md) for the source inventory and [`DOCUMENTATION.md`](DOCUMENTATION.md)
for the architecture, endpoints and UI.
