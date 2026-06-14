# Data Sources

Every fact the MiCA Compliance Copilot can cite comes from one of **four source families** — all of
them **public** data published by EU authorities or public news feeds. The copilot answers *only* from
this indexed material and abstains otherwise (see [`METHODOLOGY.md`](METHODOLOGY.md)), so what is
indexed *is* the boundary of what it can say.

| # | Source family | What it provides | Origin | Where it lands |
|---|---|---|---|---|
| 1 | **Official documents** | The Regulation + Level-2 RTS/ITS + ESMA/EBA guidelines & Q&As | EUR-Lex · ESMA · EBA | `reg_chunks` (pgvector) |
| 2 | **Full-text news** | Current EU crypto-regulation developments | 14 RSS feeds (regulators + trade press) | `news_chunks` (pgvector) |
| 3 | **ESMA registers** | Real CASP / issuer / white-paper / warning data | 5 public ESMA CSVs | `casps` · `emt_issuers` · `art_issuers` · `other_whitepapers` · `non_compliant` |
| 4 | **White-paper token reads** | The token (name + ticker) each Title II white paper concerns | The white-paper documents themselves | `other_whitepapers.token_name` / `.ticker` |

All outbound fetches identify themselves honestly with an educational, non-commercial User-Agent
(`…/0.2 (+educational; non-commercial)`).

---

## 1. Official document corpus → `reg_chunks`

The manifest is **`data/document_sources.json` — 34 curated sources**, fetched into ~300 article/section
records (`data/document_corpus.jsonl`) and chunked into **~935 vectors** in `reg_chunks`.

| Instrument type (`doc_type`) | Count | Examples (CELEX / id) |
|---|---|---|
| Base **Regulation** (MiCA) | 1 | `32023R1114` — Regulation (EU) 2023/1114 |
| Delegated Regulations (**RTS**) | 14 | `32025R0294` (complaints handling), `32025R0293` (conflicts of interest), `32025R0419` (own-funds adjustment), `32025R1264` (liquidity management) … |
| Implementing Regulations (**ITS**) | 3 | `32024R2984` (white-paper templates), `32025R0306` (CASP authorisation forms), `32024R2902` (token reporting) |
| **Guidelines** (ESMA / EBA) | 9 | financial-instrument qualification (`ESMA75453128700-1323`), reverse solicitation, suitability, systems & security, knowledge & competence; EBA recovery (`EBA/GL/2024/07`) & redemption (`EBA/GL/2024/13`) plans, liquidity stress-testing, internal governance |
| **Q&As** (ESMA / EBA) | 4 | execution services, staking, grandfathering; the EBA Single Rulebook Q&A |
| **Reports / consultation papers** (ESMA / EBA) | 3 | incl. the EBA draft liquidity-requirements consultation paper |

**By authority:** 1 EU · 14 European Commission · 11 ESMA · 8 EBA.

**Provenance & fetch.**
- **EUR-Lex** documents (Regulation + RTS/ITS) are fetched by CELEX id and **parsed article-by-article**
  (`app/rag/eurlex.py`) — each `Article N` becomes its own record with a stable EUR-Lex / ELI deep link
  (e.g. `…/eli/reg/2023/1114/oj#art_36`). Article bodies are capped at 6 000 chars; an unparseable layout
  falls back to whole-document text.
- **ESMA / EBA** guidelines & Q&As are fetched as **PDF or HTML** (`app/rag/pdf.py`): PDFs via `pypdf`,
  HTML via `trafilatura` (with a regex tag-strip fallback). Sources yielding < 200 chars are skipped.
- Timeouts: 60 s (EUR-Lex), 90 s (PDF/HTML). Failures are logged and skipped, never fatal.

**Refresh & cache.** `python -m app.register` aside, the corpus is built with
`python -m app.rag.docs_ingest` — it uses the committed `document_corpus.jsonl` cache (so the corpus
**rebuilds offline**, reproducibly, for a grader) and only re-fetches from the live sources with
`--refresh`. A minimal hand-written fallback (`data/corpus.jsonl`, 48 article summaries) covers the
fully-offline case.

**Licensing.** EUR-Lex, ESMA and EBA materials are public EU documents, reusable under the EU's reuse
policy **with attribution**; the copilot links back to the original (EUR-Lex / ESMA / EBA URL) on every
citation rather than presenting the text as its own.

---

## 2. Full-text news corpus → `news_chunks`

**14 RSS feeds** (`app/news/sources.py`). Regulator feeds are firm-wide; MiCA relevance is decided
downstream by the triage step (§ Methodology), not by the feed.

**EU regulators & national competent authorities (10):**

| Source | Feed |
|---|---|
| ESMA | `https://www.esma.europa.eu/rss.xml` |
| EBA | `https://www.eba.europa.eu/rss.xml` |
| European Commission — Finance | `https://finance.ec.europa.eu/node/1408/rss_en` |
| BaFin (DE) — news + measures | `…/rssnewsfeed.xml`, `…/RSS_Massnahmen.xml` |
| AMF (FR) — news + warnings | `…/flux-rss/display/30`, `…/flux-rss/display/28` |
| MFSA (MT) | `https://www.mfsa.mt/feed/` |
| CSSF (LU) | `https://www.cssf.lu/en/feed/` |
| AFM (NL) | `https://www.afm.nl/en/rss` |

**Trade press (4):** CoinDesk, Cointelegraph, The Block, Decrypt.

**How articles are acquired.** Conditional GET (ETag / Last-Modified; a `304` short-circuits), dedup by
normalised-URL SHA-1 (tracking params stripped), then **full article text** via `trafilatura`. Each feed
is capped at 40 newest items per poll.

**What is stored.** `NEWS_STORE=fulltext` (default) keeps the extracted article text for retrieval
accuracy; `NEWS_STORE=summary` keeps a Haiku-generated 4–6 sentence **transformative summary** instead
(copyright-safer). **Either way, every news citation links to the source and shows its publication date** —
the copilot reproduces facts and points back to the outlet; it does not republish trade-press articles.

---

## 3. ESMA registers (real public data)

Five public CSVs from ESMA's interim MiCA register, base URL
`https://www.esma.europa.eu/sites/default/files/2024-12/` (`app/register/sources.py`), synced with
`python -m app.register.sync [--refresh]` into one table each. Row counts are the current snapshot
(`data/register_snapshot.json`; total **1 258** rows = the `register_rows` you see on `/health`):

| CSV | Table | What it lists | Rows |
|---|---|---|---|
| `CASPS.csv` | `casps` | Authorised crypto-asset service providers | 215 |
| `EMTWP.csv` | `emt_issuers` | E-money-token issuers / white papers | 21 |
| `ARTZZ.csv` | `art_issuers` | Asset-referenced-token issuers | 0¹ |
| `OTHER.csv` | `other_whitepapers` | Title II "other crypto-asset" white papers | 877 |
| `NCASP.csv` | `non_compliant` | Non-compliant entities / NCA warnings | 145 |

¹ Zero ART issuers are currently in ESMA's public register — not a sync error.

Dates are parsed defensively (DD/MM/YYYY ↔ MM/DD/YYYY disambiguation), service codes normalised to the
MiCA `a`–`j` letters, and rows deduped by a deterministic primary key. The snapshot is cached so the
registers also **rebuild offline**. ESMA register data is public; the copilot attributes it and links to
the white-paper URL when one exists.

---

## 4. White-paper token reads → `other_whitepapers.token_name` / `.ticker`

ESMA's Title II register (`OTHER.csv`) records the **offeror and the white-paper URL but not the token**.
So "does Cardano / MegaETH have a MiCA white paper?" can't be answered from the CSV alone. The copilot
fills the gap by **reading each white-paper document** (`python -m app.register.whitepapers`):

1. Fetch the white paper (PDF via `pypdf`, HTML via `trafilatura`; PDF/HTML sniffed by magic bytes).
2. Send the first ~5 000 chars to **`claude-haiku-4-5`** with a strict prompt: *identify the specific
   token this white paper concerns* → `{token_name, ticker (UPPERCASE), issuer, confidence}`; invent
   nothing, return `null` + low confidence if unclear.
3. Cache to `data/wp_tokens.json` (idempotent; `--recheck` retries low/none-confidence rows). Thread
   safety: **fetch concurrently, parse single-threaded** (pypdf/lxml are not thread-safe), then classify.

**Coverage (current cache):** **556 / 877** white papers have a ticker resolved (≈ 63 %) — 540 high
confidence, the rest medium/low, and 197 fell back to an offeror-name heuristic (dead/unreadable links →
`confidence: "none"`). This is why the copilot treats **absence from the register as "not found," never
as proof of non-compliance**.

---

## 5. Sourcing posture (summary)

- **Public sources only**, fetched with an honest, non-commercial educational User-Agent.
- **Attribute and link, don't rehost** — every answer cites the EUR-Lex / ESMA / EBA / outlet URL; news
  can run in transformative-summary mode (`NEWS_STORE=summary`).
- **Reproduce facts, not opinions** — regulatory text, register rows, dated news.
- **Reproducible offline** — documents, registers and white-paper reads are all cached in `data/` and
  rebuild from cache without re-hitting the network (or paying for API calls).
- **Best-effort, dated, honest about gaps** — dead links are skipped, coverage is partial where noted,
  and the system abstains rather than guess. **General information about MiCA, not legal advice.**

## 6. Refresh cadence

| Data | Command | When |
|---|---|---|
| Documents | `python -m app.rag.docs_ingest --refresh` | On demand (sources change slowly) |
| News | `python -m app.news.poll` / `python -m app.news.scheduler` | Continuous — trade press ~10 min, regulators ~6 h |
| Registers | `python -m app.register.sync --refresh` | On demand (ESMA republishes ~weekly) |
| White-paper tokens | `python -m app.register.whitepapers [--recheck]` | After a register refresh, to fill new rows |

See [`METHODOLOGY.md`](METHODOLOGY.md) for how this data is chunked, embedded, retrieved, routed, and
evaluated.
