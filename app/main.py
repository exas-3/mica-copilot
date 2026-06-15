"""FastAPI application — the orchestration point between the UI and the GenAI layer.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs   (auto-generated Swagger/OpenAPI)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool
from app.routers import chat, classify, health, registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the write-only conversation log table exists (it is never read by the agent).
    try:
        from app.services import chatlog
        chatlog.ensure_table()
    except Exception:  # noqa: BLE001 — never block startup on logging setup
        pass
    yield
    close_pool()


app = FastAPI(
    title="MiCA Compliance Copilot",
    version="0.1.0",
    description=(
        "A RAG + agentic assistant for the EU Markets in Crypto-Assets Regulation "
        "(Regulation (EU) 2023/1114). Answers are grounded in retrieved provisions with "
        "article-level citations; an agent can also look up the ESMA register snapshot. "
        "GenAI techniques: RAG, tool/function calling, structured outputs, prompt caching."
    ),
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(classify.router)
app.include_router(registry.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "MiCA Compliance Copilot", "docs": "/docs", "health": "/health"}
