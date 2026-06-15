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
from app.services import chatlog, rag

_MAX_TOOL_ITERS = 5

_client: anthropic.Anthropic | None = None

# Signals that a chat query needs Sonnet's stronger reasoning / current-facts handling and
# must NOT be routed to Haiku: news/current status, deadlines, named entities/registers,
# white papers, enforcement, or anything abstention-prone. Conservative by design.
_SONNET_SIGNALS = (
    "news", "latest", "recent", "current", "now", "today", "deadline", "transition",
    "transitional", "grandfather", "1 july", "register", "registered", "authorised",
    "authorized", "white paper", "whitepaper", "enforcement", "flagged", "non-compliant",
    "noncompliant", "sanction", "warning", "status of", "happening",
)


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
    kw: dict = {"output_config": {"effort": get_settings().agent_effort}}
    if thinking:
        kw["thinking"] = {"type": "adaptive"}
    return kw


def _route_model(message: str, history) -> str:
    """Pick the model for a chat turn. Defaults to Sonnet; routes a clearly-simple,
    single-provision lookup to Haiku ONLY when query_routing is enabled. Anything with a
    current-facts / entity / register / enforcement signal, or any multi-turn context, stays
    on Sonnet. Caches are model-scoped, so a routed query starts a separate warm prefix."""
    s = get_settings()
    if not s.query_routing:
        return s.agent_model
    if history:  # follow-ups can reference earlier context — keep the stronger model
        return s.agent_model
    text = message.lower()
    if len(message) > 200 or any(sig in text for sig in _SONNET_SIGNALS):
        return s.agent_model
    return s.simple_query_model


def _accumulate_usage(acc: dict, usage) -> None:
    """Sum a response's token usage into an accumulator (one chat turn = several API calls)."""
    if usage is None:
        return
    for field in ("input_tokens", "output_tokens",
                  "cache_creation_input_tokens", "cache_read_input_tokens"):
        acc[field] = acc.get(field, 0) + (getattr(usage, field, 0) or 0)


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
def chat_sync(message: str, history, *, log: bool = True) -> dict:
    client = _get_client()
    s = get_settings()
    messages = _to_message_dicts(history) + [{"role": "user", "content": message}]

    tool_events: list[dict] = []
    citations: list[dict] = []
    seen_refs: set[str] = set()
    usage: dict = {}
    model = _route_model(message, history)

    for _ in range(_MAX_TOOL_ITERS):
        resp = _create(
            client,
            model=model,
            max_tokens=s.chat_max_tokens,
            system=_system_blocks(),
            tools=TOOLS,
            messages=messages,
        )
        _accumulate_usage(usage, getattr(resp, "usage", None))
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
        result = {
            "answer": answer or "(no answer produced)",
            "citations": citations,
            "tool_events": tool_events,
            "grounded": bool(citations),
            "model": model,
            "usage": usage,
        }
        if log:
            chatlog.log_turn(message, result["answer"], grounded=result["grounded"], model=model,
                             citations=citations, tool_events=tool_events, usage=usage)
        return result

    result = {
        "answer": "I couldn't complete the lookup within the allotted steps. Please rephrase the question.",
        "citations": citations,
        "tool_events": tool_events,
        "grounded": bool(citations),
        "model": model,
        "usage": usage,
    }
    if log:
        chatlog.log_turn(message, result["answer"], grounded=result["grounded"], model=model,
                         citations=citations, tool_events=tool_events, usage=usage)
    return result


# ── Streaming chat (SSE) ─────────────────────────────────────────────────────
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# A large SSE *comment* (a line starting with ":") sent first to fill a proxy's transform/response
# buffer and force an early flush, so the real token chunks that follow aren't held back to one
# burst (Cloudflare's edge buffering). A short keep-alive comment is sent between agent turns to
# flush the gap while a tool runs. Comments are ignored by EventSource and by our client parser
# (frontend/lib/api.ts only reads lines starting with "data:"), so they are invisible to the UI.
_SSE_PRIMER = ": " + " " * 2048 + "\n\n"
_SSE_KEEPALIVE = ": keep-alive\n\n"


def stream_chat(message: str, history) -> Iterator[str]:
    try:
        client = _get_client()
    except RuntimeError as e:
        yield _sse({"type": "error", "message": str(e)})
        return

    s = get_settings()
    messages = _to_message_dicts(history) + [{"role": "user", "content": message}]
    citations: list[dict] = []
    tool_events: list[dict] = []
    seen_refs: set[str] = set()
    usage: dict = {}
    model = _route_model(message, history)

    try:
        yield _SSE_PRIMER  # prime proxy buffers so the first real token isn't held back
        for _ in range(_MAX_TOOL_ITERS):
            yield _SSE_KEEPALIVE  # flush the gap before each model turn (e.g. while a tool runs)
            pending: list[str] = []
            with _open_stream(
                client,
                model=model,
                max_tokens=s.chat_max_tokens,
                system=_system_blocks(),
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    pending.append(text)
                    yield _sse({"type": "token", "text": text})
                final = stream.get_final_message()
            _accumulate_usage(usage, getattr(final, "usage", None))

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
                        tool_events.append({"tool": block.name, "input": block.input or {}, "summary": out["summary"]})
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
            answer_text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text").strip()
            yield _sse({"type": "citations", "citations": citations, "grounded": bool(citations)})
            yield _sse({"type": "usage", "model": model, "usage": usage})
            chatlog.log_turn(message, answer_text, grounded=bool(citations), model=model,
                             citations=citations, tool_events=tool_events, usage=usage)
            yield _sse({"type": "done"})
            return

        yield _sse({"type": "citations", "citations": citations, "grounded": bool(citations)})
        yield _sse({"type": "usage", "model": model, "usage": usage})
        chatlog.log_turn(message, "", grounded=bool(citations), model=model,
                         citations=citations, tool_events=tool_events, usage=usage)
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
    # (passing it via **kwargs *and* as a keyword raises TypeError). Structured output over
    # retrieved provisions is low-risk on Haiku, so /classify uses the cheaper classify_model.
    kwargs = dict(model=s.classify_model, max_tokens=2048, system=_system_blocks())
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
