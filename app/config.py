"""Application settings, loaded from environment / .env.

Centralises every tunable so the rest of the code never reads os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://mica:mica@127.0.0.1:5433/mica"

    # Claude
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-4-6"  # cost-effective default; claude-opus-4-8 for max quality
    cheap_model: str = "claude-haiku-4-5"
    # Token-efficiency knobs (see docs/METHODOLOGY.md). The agent loop spends most of its
    # tokens on output (adaptive thinking + answer); these cut that without losing correctness.
    agent_effort: str = "low"          # output_config.effort for the chat loop: low|medium|high|max
    chat_max_tokens: int = 1536        # max_tokens cap for chat turns (answers are terse by design)
    # Model routing — push cheap/structured sub-tasks to Haiku ($1/$5 vs Sonnet $3/$15).
    classify_model: str = "claude-haiku-4-5"      # /classify is structured + RAG-grounded → safe on Haiku
    simple_query_model: str = "claude-haiku-4-5"  # used by chat routing when query_routing is on
    query_routing: bool = False        # off until eval-validated: route clearly-simple lookups to Haiku

    # Embeddings
    embedder: str = "local"  # "voyage" | "local"
    voyage_api_key: str = ""
    voyage_model: str = "voyage-law-2"
    local_embed_model: str = "mixedbread-ai/mxbai-embed-large-v1"
    embed_dim: int = 1024
    local_query_prefix: str = ""  # query-side instruction; empty → derived (mxbai is asymmetric, needs one)

    # Retrieval
    top_k: int = 20      # candidates pulled from pgvector
    return_k: int = 6    # chunks kept after rerank and handed to the model
    retrieval_mode: str = "vector"   # "vector" | "hybrid" (cosine + lexical tsv, RRF); vector wins on the eval
    rerank: str = "off"              # "off" | "local" | "voyage" (cross-encoder over a larger pool)
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"  # key-free local cross-encoder
    rerank_pool: int = 40            # candidates fetched before reranking down to return_k
    # Source-diversity selection: stop one document (e.g. an RTS or ESMA guideline) from
    # crowding out the base article it elaborates. Reserve slots for the top base-regulation
    # provisions, then fill capping any one source document.
    retrieval_diversity: bool = False  # off: net-negative on the eval (broke Art 59 / 4-5); kept as an option
    diversity_pool: int = 150        # candidates fetched before diverse selection
    reserve_base: int = 2            # slots reserved for top base-regulation provisions
    max_per_doc: int = 2             # max chunks from a single source document in the result

    # Document corpus (official regulation + ESMA/EBA RTS/ITS/guidelines/Q&As)
    document_sources_path: str = "data/document_sources.json"
    document_corpus_path: str = "data/document_corpus.jsonl"

    # ESMA registers (real CSV sync) + white-paper token extraction
    register_snapshot_path: str = "data/register_snapshot.json"
    wp_tokens_path: str = "data/wp_tokens.json"
    wp_extract_workers: int = 12  # concurrency for reading white-paper documents

    # News pipeline
    news_store: str = "fulltext"        # "fulltext" | "summary" (Haiku transformative summary)
    news_return_k: int = 6              # news chunks handed to the model
    news_recency_halflife_days: float = 21.0  # recency decay in the blended news score
    news_max_articles_per_feed: int = 40      # cap per poll, newest first
    news_press_minutes: int = 10        # press poll cadence (scheduler)
    news_regulators_hours: int = 6      # regulator poll cadence (scheduler)

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def has_claude(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def effective_local_query_prefix(self) -> str:
        """Query instruction for the local embedder. mxbai-embed-large-v1 is asymmetric and
        expects queries (not documents) to carry this prompt; fastembed does NOT add it.
        Set LOCAL_QUERY_PREFIX="none" to disable (used by the eval ablation)."""
        if self.local_query_prefix == "none":
            return ""
        if self.local_query_prefix:
            return self.local_query_prefix
        if "mxbai" in self.local_embed_model.lower():
            return "Represent this sentence for searching relevant passages: "
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
