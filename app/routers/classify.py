"""Structured classification endpoint — token/service → MiCA category as JSON."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    Citation,
    ClassifyRequest,
    ClassifyResponse,
    ObligationItem,
    ServiceMatch,
)
from app.services import llm
from app.services.ratelimit import rate_limit

router = APIRouter(tags=["classify"])


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    summary="Classify a token/service under MiCA",
    dependencies=[Depends(rate_limit)],
)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    if not get_settings().has_claude:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured.")
    try:
        data = llm.classify(req.description)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Classification failed: {e}")

    try:
        return ClassifyResponse(
            asset_type=data.get("asset_type", "uncertain"),
            asset_rationale=data.get("asset_rationale", ""),
            services=[ServiceMatch(**s) for s in data.get("services", []) if isinstance(s, dict)],
            obligations=[ObligationItem(**o) for o in data.get("obligations", []) if isinstance(o, dict)],
            citations=[Citation(**c) for c in data.get("citations", []) if isinstance(c, dict)],
            confidence=data.get("confidence", "low"),
        )
    except ValidationError:
        # The model returned something off-schema; degrade gracefully rather than 500.
        return ClassifyResponse(
            asset_type="uncertain",
            asset_rationale=data.get("asset_rationale", "Could not produce a schema-valid classification."),
            services=[],
            obligations=[],
            citations=[],
            confidence="low",
        )
