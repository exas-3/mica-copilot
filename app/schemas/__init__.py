"""Pydantic request/response schemas — the backend's clean public contract.

These also drive the auto-generated Swagger/OpenAPI docs at /docs.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Shared ────────────────────────────────────────────────────────────────────
class Citation(BaseModel):
    kind: str = Field("document", description="document | news")
    article_ref: str = Field("", examples=["Article 36"])
    title: str = Field("", examples=["Requirements for the reserve of assets"])
    source: str = Field("mica", description="Corpus this chunk came from")
    doc_type: str = Field("", description="regulation | rts | its | guideline | qa | report (documents)")
    source_name: str = Field("", description="News outlet / regulator name (news)")
    published_at: str = Field("", description="Publication date YYYY-MM-DD (news)")
    source_url: str = Field("", description="Deep link to the provision or article")
    snippet: str = Field("", description="Short excerpt of the cited text")


class ToolEvent(BaseModel):
    tool: str = Field(..., examples=["search_regulation"])
    input: dict = Field(default_factory=dict)
    summary: str = Field("", description="Human-readable one-liner for the UI trace")


# ── /chat ─────────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["What are the reserve requirements for an EMT issuer?"])
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    grounded: bool = Field(True, description="False when the model abstained for lack of supporting context")


# ── /classify ─────────────────────────────────────────────────────────────────
class ClassifyRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=1,
        examples=["A token pegged 1:1 to the euro, redeemable at par, backed by bank deposits and short-term EU government bonds."],
    )


class ServiceMatch(BaseModel):
    code: str = Field(..., description="MiCA crypto-asset service letter (a–j)")
    name: str
    applies: bool


class ObligationItem(BaseModel):
    obligation: str
    article_ref: str = ""


class ClassifyResponse(BaseModel):
    asset_type: Literal[
        "asset-referenced token (ART)",
        "e-money token (EMT)",
        "other crypto-asset",
        "out of scope of MiCA",
        "uncertain",
    ]
    asset_rationale: str
    services: list[ServiceMatch] = Field(default_factory=list)
    obligations: list[ObligationItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]


# ── /registry/search ──────────────────────────────────────────────────────────
class RegistryEntry(BaseModel):
    kind: str = Field(..., description="casp | emt_issuer | art_issuer | whitepaper | non_compliant")
    name: str
    country: Optional[str] = None
    source_url: Optional[str] = None
    detail: Optional[str] = None


class RegistrySearchResponse(BaseModel):
    query: str
    results: list[RegistryEntry] = Field(default_factory=list)


# ── /health ───────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    claude_configured: bool
    embedder: str
    chunks_indexed: int
    news_indexed: int
    register_rows: int
