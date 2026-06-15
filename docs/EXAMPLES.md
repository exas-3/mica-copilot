# Usage Examples

Copy-paste examples for every part of the MiCA Compliance Copilot: each API endpoint (request **and**
response), the streaming event protocol, the two UI flows, and the evaluation harness.

Responses below are **illustrative** — exact wording, article numbers, citations and dates depend on
what is indexed at the time you run the query. Field *shapes* are exact (they come from the pydantic
schemas in `app/schemas/__init__.py`).

> **Setup first.** Bring the stack up and index the corpora as in [`../README.md`](../README.md) §2 (or
> `make db && make docs && make news && make register`), then start the backend (`make api`) and,
> optionally, the UI (`make ui`).

---

## 0. Health / readiness

Confirms the key is configured and shows how much data is indexed. Use this to verify ingestion worked
before anything else.

```bash
curl -s localhost:8000/health | jq
```

```json
{
  "status": "ok",
  "claude_configured": true,
  "embedder": "local",
  "chunks_indexed": 1422,
  "news_indexed": 63,
  "register_rows": 1258
}
```

`chunks_indexed` is the **document** corpus (regulation + RTS/ITS + ESMA/EBA), `news_indexed` is the
**full-text news** corpus, `register_rows` is the synced ESMA registers. All three should be `> 0`.

---

## 1. Ask MiCA — synchronous JSON (`POST /chat/sync`)

The simplest way to exercise the agent: one request, one JSON response. Good for scripts and for graders.

**Request**

```bash
curl -s localhost:8000/chat/sync -H 'content-type: application/json' \
  -d '{"message":"What must back the reserve of an asset-referenced token?"}' | jq
```

**Response** (`ChatResponse`)

```json
{
  "answer": "An issuer of an asset-referenced token must constitute and maintain at all times a reserve of assets ... [grounded answer, citing the article].",
  "citations": [
    {
      "kind": "document",
      "article_ref": "Article 36",
      "title": "Requirements for the reserve of assets",
      "source": "mica",
      "doc_type": "regulation",
      "source_name": "",
      "published_at": "",
      "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114#art_36",
      "snippet": "Issuers of asset-referenced tokens shall constitute and maintain ... a reserve of assets."
    }
  ],
  "tool_events": [
    { "tool": "search_regulation", "input": { "query": "reserve of assets asset-referenced token" }, "summary": "Searched MiCA corpus" }
  ],
  "grounded": true
}
```

- `citations[]` — every source the answer is grounded in. `kind` is `document` or `news`; documents
  carry `article_ref` + `doc_type`, news carry `source_name` + `published_at`.
- `tool_events[]` — the agent's tool-use trace (which tools it called and why).
- `grounded` — `false` means the agent abstained (see §5).
- `model` + `usage` — the response also returns the model id (`claude-sonnet-4-6`) and the per-turn
  token `usage` (`input_tokens` / `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens`),
  the same payload the streaming endpoint emits as a `usage` event.

### Routing examples (one request each)

The agent decides **which** corpus answers the question. These three exercise the different routes:

```bash
# Level-1 regulation:
curl -s localhost:8000/chat/sync -H 'content-type: application/json' \
  -d '{"message":"Must an e-money token be redeemable at par value?"}' \
  | jq '.answer, .citations[].article_ref'

# Level-2 RTS/ITS (document corpus beyond the base regulation):
curl -s localhost:8000/chat/sync -H 'content-type: application/json' \
  -d '{"message":"Which Delegated Regulation sets the complaints-handling RTS for CASPs?"}' \
  | jq '.citations[].article_ref'

# Current facts → news + register routing (note the dated citations):
curl -s localhost:8000/chat/sync -H 'content-type: application/json' \
  -d '{"message":"What is going on with Binance and MiCA, and is there a deadline?"}' \
  | jq '.tool_events[].summary, (.citations[] | {source_name, published_at})'
```

The Binance query is the one that motivated the news corpus: it should surface **Article 143** (the
transitional / grandfathering regime) and the **1 July 2026** deadline, with dated news citations.

---

## 2. Ask MiCA — streaming (`POST /chat`, Server-Sent Events)

The UI uses this. Same input as `/chat/sync`; the response is an SSE stream of `data: {json}` lines.

```bash
curl -N -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"Do holders of an asset-referenced token have a right of redemption?"}'
```

```
data: {"type": "tool", "tool": "search_regulation", "summary": "Searched MiCA corpus"}

data: {"type": "token", "text": "Yes. Under "}

data: {"type": "token", "text": "Article 39, holders have a permanent right of redemption ..."}

data: {"type": "citations", "citations": [ { "kind": "document", "article_ref": "Article 39", "...": "..." } ], "grounded": true}

data: {"type": "usage", "model": "claude-sonnet-4-6", "usage": {"input_tokens": 4073, "output_tokens": 643, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 6371}}

data: {"type": "done"}
```

> The stream opens with a ~2 KB SSE comment "primer" (`: ` followed by spaces) to flush intermediate
> proxy buffers, and emits `: keep-alive` comments between tool-loops so the connection isn't dropped.
> SSE comment lines (starting with `:`) carry no event and are ignored by `EventSource` clients.

**Event types** (`type` field):

| Event | Payload | Meaning |
|---|---|---|
| `tool` | `tool`, `input?`, `summary?` | The agent invoked a tool (shown as a chip in the UI). |
| `token` | `text` | An answer text delta — append in order. |
| `reset` | — | Discard any streamed text so far (a pre-tool preamble; the final answer follows). |
| `thought` | `text` | The discarded preamble, surfaced separately as the agent's "thinking" (optional to render). |
| `citations` | `citations[]`, `grounded` | The sources cited + the grounded flag. |
| `usage` | `model`, `usage` (`input_tokens` / `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens`) | Per-turn token usage, emitted just before `done`. |
| `done` | — | Stream complete. |
| `error` | `message` | Something failed; stop reading. |

The `reset`/`thought` pair exists because the model sometimes emits a sentence *before* deciding to call
a tool — the UI clears that draft (`reset`) and shows it as a thought, so the final answer isn't polluted.

---

## 3. Classify a token/service (`POST /classify`) — structured output

Returns a JSON-schema-constrained classification (never free text). The response always validates against
`ClassifyResponse`.

**Request**

```bash
curl -s localhost:8000/classify -H 'content-type: application/json' \
  -d '{"description":"A token pegged 1:1 to the euro, redeemable at par, backed by bank deposits and short-term EU government bonds."}' | jq
```

**Response** (`ClassifyResponse`)

```json
{
  "asset_type": "e-money token (EMT)",
  "asset_rationale": "It references a single official currency (the euro) and is redeemable at par, which is the defining feature of an e-money token under MiCA.",
  "services": [
    { "code": "a", "name": "Custody and administration of crypto-assets", "applies": false },
    { "code": "g", "name": "Execution of orders for clients", "applies": false }
  ],
  "obligations": [
    { "obligation": "Issuer must be an authorised credit institution or e-money institution.", "article_ref": "Article 48" },
    { "obligation": "Holders have a claim and a right of redemption at par value at any time.", "article_ref": "Article 49" }
  ],
  "citations": [
    { "kind": "document", "article_ref": "Article 48", "title": "...", "source": "mica", "doc_type": "regulation", "source_url": "https://eur-lex.europa.eu/...", "snippet": "..." }
  ],
  "confidence": "high"
}
```

- `asset_type` is one of: `asset-referenced token (ART)`, `e-money token (EMT)`, `other crypto-asset`,
  `out of scope of MiCA`, `uncertain`.
- `services[]` covers the MiCA crypto-asset services a–j (`applies` flags the ones implicated).
- `obligations[]` are tied to articles; `citations[]` ground the classification; `confidence` ∈ low/medium/high.

Try also: an out-of-scope item (e.g. *"a one-of-a-kind digital artwork NFT"* → `other crypto-asset` /
`out of scope`) and an ART (*"a token backed by a basket of USD, EUR and gold"* → `asset-referenced token (ART)`).

---

## 4. Search the ESMA registers (`GET /registry/search`) — no LLM

A deterministic lookup over the **real** synced ESMA registers: CASPs, EMT/ART issuers, Title II
white papers (with the token name/ticker **read from each white-paper document**), and warnings.

```bash
curl -s 'localhost:8000/registry/search?q=Cardano' | jq
```

**Response** (`RegistrySearchResponse`)

```json
{
  "query": "Cardano",
  "results": [
    {
      "kind": "whitepaper",
      "name": "Cardano (ADA)",
      "country": "IE",
      "source_url": "https://www.esma.europa.eu/.../cardano-whitepaper.pdf",
      "detail": "Title II crypto-asset white paper · token ADA"
    }
  ]
}
```

This is the lookup that fixed *"does Cardano/MegaETH have a MiCA white paper?"* — because the token name
and ticker are read from the document itself, both the **name** (`Cardano`) and the **ticker** (`ADA` /
`MEGA`) match. `kind` ∈ `casp | emt_issuer | art_issuer | whitepaper | non_compliant`.

```bash
# A few more:
curl -s 'localhost:8000/registry/search?q=MEGA'   | jq '.results[] | {kind, name}'   # MegaETH white paper
curl -s 'localhost:8000/registry/search?q=Kraken' | jq '.results[] | {kind, name, country}'  # authorised CASP(s)
```

---

## 5. Abstention (the point of the project)

In a compliance setting a confident-but-wrong answer is worse than "I don't know." Ask something the
corpus can't support and the agent declines instead of inventing:

```bash
curl -s localhost:8000/chat/sync -H 'content-type: application/json' \
  -d '{"message":"What are the capital gains tax rates for crypto in Greece?"}' \
  | jq '.grounded, .answer'
```

```json
false
"That isn't covered by the MiCA materials I can cite, so I won't guess. MiCA does not govern national tax treatment ..."
```

`grounded: false` (no citations) is the signal the UI renders as a *"No grounding — answer withheld"* badge.

---

## 6. The UI

```bash
cd frontend && npm install && npm run dev      # http://localhost:3000
```

- **Ask MiCA** (`/`) — type a question; tool calls appear as chips ("Searched MiCA corpus", "Searched
  news"), the answer streams token-by-token and renders as **Markdown** (bold, lists, tables, code,
  links), and a **Citations** panel groups sources into
  **Regulation & documents** (article + EUR-Lex/PDF link) and **News** (outlet + date + link). Example
  prompts are one click away so a reviewer can hit every path:
  - *"What must back the reserve of an asset-referenced token?"* → regulation
  - *"What is going on with Binance and MiCA, and is there a deadline?"* → news + register
  - *"What are the tax rules for crypto in Greece?"* → abstains
- **Classify** (`/classify`) — paste a token/service description → a structured card (asset type, the
  a–j services, the obligations each tied to an article, and citations).
- **Guides** (`/guides`) — four cited MiCA explainers: ART, EMT vs. stablecoin, CASP authorisation,
  white-paper requirements.
- **Docs** (`/docs`) — an in-app documentation reader.
- **Privacy** (`/privacy`) and **Terms** (`/terms`) — the privacy policy and terms of use.

The UI points at `http://localhost:8000` by default — override with `NEXT_PUBLIC_API_URL` (see
`frontend/.env.local.example`).

---

## 7. Evaluation harness

```bash
python -m eval.run --e2e --judge        # or: make eval
```

Runs the golden set (`eval/goldens.jsonl`, **44 questions**) end-to-end through the live agent and scores
retrieval, citation, abstention, register lookup, and (LLM-as-judge) faithfulness. Latest run
(v2 corpus: 1,422 regulation + 63 news chunks, 1,258 register rows; agent = Sonnet 4.6 at `effort=low`,
judge = Haiku 4.5, embedder = local `mxbai-embed-large-v1`):

| Metric | Score |
|---|---|
| retrieval_hit@k | 0.971 |
| citation_hit | 0.914 |
| abstention_accuracy | 1.00 |
| faithfulness | 0.886 |
| register_hit | 1.00 |

Per-question detail is written to `eval/results/scorecard.json`. See
[`DOCUMENTATION.md`](DOCUMENTATION.md) §8 for what each metric measures and why the strict exact-article
hit is lower against the richer Level-2 corpus.

---

## 8. Swagger / OpenAPI

Every endpoint above is also explorable interactively (with the pydantic schemas as the contract) at:

```
http://localhost:8000/docs
```
