"""ESMA register snapshot search — a thin, deterministic lookup (no LLM)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import RegistryEntry, RegistrySearchResponse
from app.services import registry as registry_svc

router = APIRouter(tags=["registry"])


@router.get("/registry/search", response_model=RegistrySearchResponse, summary="Search the ESMA register snapshot")
def search(q: str = Query(..., min_length=1, description="Entity or token name")) -> RegistrySearchResponse:
    rows = registry_svc.search_registry(q)
    return RegistrySearchResponse(
        query=q,
        results=[RegistryEntry(**r) for r in rows],
    )
