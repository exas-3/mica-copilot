# Documentation

| File | What's in it |
|---|---|
| [`DOCUMENTATION.md`](DOCUMENTATION.md) | The full project document — title/purpose, use scenario, technologies & rationale, architecture + data flow, endpoints & services, UI, GenAI techniques (RAG · agents/tool-calling · structured outputs · prompt caching), evaluation results, limitations & future work, and a deliverables-mapping checklist. **Export this to PDF for the assignment submission.** |
| [`EXAMPLES.md`](EXAMPLES.md) | Copy-paste usage examples — every endpoint with request **and** response, the SSE event protocol, the two UI flows, abstention, and the eval run. |
| [`DATA-SOURCES.md`](DATA-SOURCES.md) | Every data source the copilot can cite — the 34 official documents, the 14 news feeds, the 5 ESMA registers, the white-paper token reads — with provenance, licensing posture, and refresh cadence. |
| [`METHODOLOGY.md`](METHODOLOGY.md) | How the data becomes grounded answers — ingestion, chunking, embeddings, vector store, retrieval (incl. the news blended-score formula), agent routing, grounding/abstention, structured output, and the evaluation method. |
| [`architecture.svg`](architecture.svg) | The architecture diagram (UI → FastAPI → Claude agent loop → tools → Postgres/pgvector). |

For install/run instructions and the project overview, see the top-level [`../README.md`](../README.md).
