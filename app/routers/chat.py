"""Chat endpoints — streaming (SSE) and synchronous (JSON)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse
from app.services import llm

router = APIRouter(tags=["chat"])


@router.post("/chat", summary="Ask MiCA — streamed (Server-Sent Events)")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream the grounded answer as SSE.

    Event payloads (`data: {json}`):
      - `{"type":"tool", ...}`      a tool the agent invoked (regulation search / register lookup)
      - `{"type":"token","text":…}` an answer text delta
      - `{"type":"citations", ...}` the provisions cited + `grounded` flag
      - `{"type":"done"}` / `{"type":"error","message":…}`
    """
    return StreamingResponse(
        llm.stream_chat(req.message, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sync", response_model=ChatResponse, summary="Ask MiCA — single JSON response")
def chat_sync(req: ChatRequest) -> ChatResponse:
    if not get_settings().has_claude:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured.")
    try:
        result = llm.chat_sync(req.message, req.history)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return ChatResponse(**result)
