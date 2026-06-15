"""Claude integration: the agentic tool loop, SSE streaming, and structured classify.

Design notes
------------
* Model: Sonnet 4.6 by default for the agent loop (adaptive thinking + effort); set
  AGENT_MODEL=claude-opus-4-8 for max quality. Haiku 4.5 handles cheap sub-tasks.
* Prompt caching: the large, stable SYSTEM_PROMPT carries ``cache_control`` so it is
  cached across requests; per-question retrieved context arrives only inside the
  conversation turns, after the cached prefix.
* Tool loop: standard manual agentic loop — call the model, run any ``tool_use`` blocks
  locally, feed ``tool_result`` back, repeat until the model answers. Assistant content
  (including thinking blocks) is echoed back verbatim, as required on the same model.
* Streaming: the loop streams the final answer's text deltas over SSE; tool calls surface
  as discrete events so the UI can show the agent's trace.
"""
from __future__ import annotations

import json
from typing import Iterator

import anthropic

from app.agents.prompts import (
    CLASSIFY_INSTRUCTIONS,
    MICA_CLASSIFICATION_SCHEMA,
    SYSTEM_PROMPT,
)
from app.agents.tools import TOOLS, run_tool
from app.config import get_settings
from app.services import rag

_MAX_TOOL_ITERS = 5
_EFFORT = "medium"  # balance of quality vs. latency for an interactive copilot

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    s = get_settings()
    if not s.has_claude:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — /chat and /classify are unavailable.")
    if _client is None:
        _client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    return _client


def _system_blocks() -> list[dict]:
    # cache_control on the last (only) system block caches the whole stable prefix.
    return [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


def _advanced_kwargs(thinking: bool = True) -> dict:
    kw: dict = {"output_config": {"effort": _EFFORT}}
    if thinking:
        kw["thinking"] = {"type": "adaptive"}
    return kw


def _create(client: anthropic.Anthropic, *, thinking: bool = True, **kwargs):
    """messages.create, tolerant of SDK versions that don't know the newest params."""
    try:
        return client.messages.create(**kwargs, **_advanced_kwargs(thinking))
    except TypeError:
        return client.messages.create(**kwargs)


def _open_stream(client: anthropic.Anthropic, *, thinking: bool = True, **kwargs):
    """messages.stream context manager, with the same advanced-param tolerance."""
    try:
        return client.messages.stream(**kwargs, **_advanced_kwargs(thinking))
    except TypeError:
        return client.messages.stream(**kwargs)


def _to_message_dicts(history) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in history]


# ── Synchronous chat (full agent loop, JSON response) ────────────────────────
def chat_sync(message: str, history) -> dict:
    client = _get_client()
    s = get_settings()
    messages = _to_message_dicts(history) + [{"role": "user", "content": message}]

    tool_events: list[dict] = []
    citations: list[dict] = []
    seen_refs: set[str] = set()

    for _ in range(_MAX_TOOL_ITERS):
        resp = _create(
            client,
            model=s.agent_model,
            max_tokens=4096,
            system=_system_blocks(),
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = run_tool(block.name, block.input or {})
                    tool_events.append({"tool": block.name, "input": block.input or {}, "summary": out["summary"]})
                    for c in out.get("citations", []):
                        key = c.get("source_url") or c.get("article_ref", "")
                        if key and key not in seen_refs:
                            seen_refs.add(key)
                            citations.append(c)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": out["content"]})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Final answer
        answer = "".join(b.text for b in resp.content if b.type == "text").strip()
        return {
            "answer": answer or "(no answer produced)",
            "citations": citations,
            "tool_events": tool_events,
            "grounded": bool(citations),
        }

    return {
        "answer": "I couldn't complete the lookup within the allotted steps. Please rephrase the question.",
        "citations": citations,
        "tool_events": tool_events,
        "grounded": bool(citations),
    }


# ── Streaming chat (SSE) ─────────────────────────────────────────────────────
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_chat(message: str, history) -> Iterator[str]:
    try:
        client = _get_client()
    except RuntimeError as e:
        yield _sse({"type": "error", "message": str(e)})
        return

    s = get_settings()
    messages = _to_message_dicts(history) + [{"role": "user", "content": message}]
    citations: list[dict] = []
    seen_refs: set[str] = set()

    try:
        for _ in range(_MAX_TOOL_ITERS):
            pending: list[str] = []
            with _open_stream(
                client,
                model=s.agent_model,
                max_tokens=4096,
                system=_system_blocks(),
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    pending.append(text)
                    yield _sse({"type": "token", "text": text})
                final = stream.get_final_message()

            if final.stop_reason == "tool_use":
                # Any text streamed this turn was preamble before a tool call, not the
                # answer. Tell the UI to discard it (so it doesn't glue onto the final
                # answer, matching chat_sync), and surface it as a "thought" trace.
                if pending:
                    yield _sse({"type": "reset"})
                    preamble = "".join(pending).strip()
                    if preamble:
                        yield _sse({"type": "thought", "text": preamble})
                messages.append({"role": "assistant", "content": final.content})
                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        out = run_tool(block.name, block.input or {})
                        yield _sse({"type": "tool", "tool": block.name,
                                    "input": block.input or {}, "summary": out["summary"]})
                        for c in out.get("citations", []):
                            key = c.get("source_url") or c.get("article_ref", "")
                            if key and key not in seen_refs:
                                seen_refs.add(key)
                                citations.append(c)
                        tool_results.append(
                            {"type": "tool_result", "tool_use_id": block.id, "content": out["content"]}
                        )
                messages.append({"role": "user", "content": tool_results})
                continue

            # Final answer already streamed as tokens above.
            yield _sse({"type": "citations", "citations": citations, "grounded": bool(citations)})
            yield _sse({"type": "done"})
            return

        yield _sse({"type": "citations", "citations": citations, "grounded": bool(citations)})
        yield _sse({"type": "done"})
    except anthropic.APIError as e:
        yield _sse({"type": "error", "message": f"Claude API error: {e}"})
    except Exception as e:  # noqa: BLE001 — surface a clean SSE error to the UI
        yield _sse({"type": "error", "message": f"Unexpected error: {e}"})


# ── Structured classification (RAG-grounded → JSON schema) ───────────────────
def classify(description: str) -> dict:
    client = _get_client()
    s = get_settings()

    chunks = rag.retrieve_for_answer(
        f"classification obligations for: {description}"
    )
    context = rag.build_context(chunks)
    grounding_citations = rag.to_citations(chunks)

    user = (
        f"{CLASSIFY_INSTRUCTIONS}\n\n"
        f"=== Retrieved MiCA provisions ===\n{context}\n\n"
        f"=== Item to classify ===\n{description}"
    )

    # `messages` is passed explicitly in each branch so it is never supplied twice
    # (passing it via **kwargs *and* as a keyword raises TypeError).
    kwargs = dict(model=s.agent_model, max_tokens=2048, system=_system_blocks())
    try:
        resp = client.messages.create(
            **kwargs,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": MICA_CLASSIFICATION_SCHEMA}},
        )
    except TypeError:
        # Older SDK without output_config: ask for JSON in-prompt as a fallback.
        resp = client.messages.create(
            **kwargs,
            messages=[{"role": "user", "content": user + "\n\nReturn ONLY a JSON object matching the required schema."}],
        )

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    data: dict = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last-ditch: extract the outermost JSON object.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = {}
    if not isinstance(data, dict):
        data = {}  # model returned a JSON array/scalar — degrade cleanly downstream

    # Merge the grounding citations so the UI always has source links, even if the
    # model returned a slimmer citation set.
    model_refs = {c.get("article_ref") for c in data.get("citations", [])}
    for gc in grounding_citations:
        if gc["article_ref"] not in model_refs:
            data.setdefault("citations", []).append(
                {"article_ref": gc["article_ref"], "title": gc["title"], "source_url": gc["source_url"]}
            )
    return data
