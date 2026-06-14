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

    # Embeddings
    embedder: str = "local"  # "voyage" | "local"
    voyage_api_key: str = ""
    voyage_model: str = "voyage-law-2"
    local_embed_model: str = "mixedbread-ai/mxbai-embed-large-v1"
    embed_dim: int = 1024

    # Retrieval
    top_k: int = 20      # candidates pulled from pgvector
    return_k: int = 6    # chunks kept after (optional) rerank and handed to the model

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
