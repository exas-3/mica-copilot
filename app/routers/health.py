"""Liveness + readiness: confirms keys, embedder, and how much data is indexed."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.news.store import count_articles
from app.rag.store import count_chunks
from app.schemas import HealthResponse
from app.services.registry import register_row_count

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(
        status="ok",
        claude_configured=s.has_claude,
        embedder=s.embedder,
        chunks_indexed=count_chunks(),
        news_indexed=count_articles(),
        register_rows=register_row_count(),
    )
