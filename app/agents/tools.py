"""Agent tools: definitions handed to Claude + the local dispatcher that runs them.

Each tool description is prescriptive about *when* to call it (recent Claude models
reach for tools conservatively, so the trigger condition belongs in the description).
"""
from __future__ import annotations

from app.services import news, rag, registry

# ── Tool definitions (Messages API `tools`) ──────────────────────────────────
TOOLS = [
    {
        "name": "search_regulation",
        "description": (
            "Semantic search over the indexed MiCA document corpus — the Regulation (EU) "
            "2023/1114 itself PLUS the Level-2/3 measures (Commission Delegated/Implementing "
            "Regulations / RTS & ITS, and ESMA/EBA guidelines and Q&As). Call this for any "
            "question about what the LAW REQUIRES: rules, definitions, obligations, thresholds, "
            "authorisation, reserves, redemption, white papers, services, technical standards. "
            "Returns the most relevant provisions with references — base your answer on these and "
            "cite them. You may call it multiple times with refined queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The regulatory question or keywords to search for."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_news",
        "description": (
            "Search a corpus of recent crypto-regulation NEWS — full-text articles from EU "
            "regulators and trade press (CoinDesk, Cointelegraph, The Block, Decrypt). Call this "
            "for CURRENT status / recent developments / 'what's happening with <entity>' / "
            "deadlines / whether a named firm has lately obtained or lost CASP authorisation. "
            "Results are dated — cite the source name and date, and treat them as reported facts, "
            "not as the text of the law. Use the optional `entity` (e.g. 'Binance') to focus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search the news corpus for."},
                "entity": {"type": "string", "description": "Optional firm/token name to focus on, e.g. 'Binance'."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_register",
        "description": (
            "Search the real ESMA MiCA registers by firm OR token name/ticker: authorised CASPs, "
            "e-money & asset-referenced token issuers, Title II crypto-asset **white papers** "
            "(matched by the token name/ticker read from the white-paper document, the offeror, or "
            "the white-paper URL), and flagged entities. Call this whenever the user asks whether a "
            "named firm, token, or coin (e.g. 'Cardano', 'ADA', 'MegaETH') is authorised/registered "
            "or has a published MiCA white paper. Returns the white-paper URL when found. "
            "Absence is informative: if a whole category is empty (e.g. no asset-referenced-token "
            "issuer has been authorised under Title III yet), report it as current market status, "
            "not as missing data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Firm, token, or ticker to look up (e.g. 'Cardano', 'ADA')."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_enforcement",
        "description": (
            "Search the non-compliant-entity / warning list for a named entity. Call this when "
            "the user asks about enforcement actions, warnings, or whether an entity has been "
            "flagged by a national competent authority."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity name to check for enforcement / warnings."}
            },
            "required": ["entity"],
        },
        # cache_control on the last tool caches the whole (stable) TOOLS block alongside
        # the cached system prompt, so every turn after the first pays cache-read on both.
        "cache_control": {"type": "ephemeral"},
    },
]


# ── Dispatcher ────────────────────────────────────────────────────────────────
def run_tool(name: str, tool_input: dict) -> dict:
    """Execute a tool. Returns {content, summary, citations} where `content` is the
    text fed back to the model and `citations` are chunk dicts for the UI panel."""
    if name == "search_regulation":
        query = (tool_input or {}).get("query", "").strip()
        chunks = rag.retrieve_for_answer(query) if query else []
        return {
            "content": rag.build_context(chunks),
            "summary": f"Searched MiCA corpus for “{query}” → {len(chunks)} provision(s)",
            "citations": rag.to_citations(chunks),
        }

    if name == "search_news":
        query = (tool_input or {}).get("query", "").strip()
        entity = ((tool_input or {}).get("entity") or "").strip() or None
        rows = news.retrieve_news(query, entity) if query else []
        return {
            "content": news.build_news_context(rows),
            "summary": f"Searched news for “{query}”" + (f" [{entity}]" if entity else "") + f" → {len(rows)} article(s)",
            "citations": news.to_news_citations(rows),
        }

    if name == "lookup_register":
        query = (tool_input or {}).get("query", "").strip()
        results = registry.search_registry(query) if query else []
        if results:
            lines = []
            for r in results:
                loc = f", {r['country']}" if r.get("country") else ""
                link = f" — {r['source_url']}" if r.get("source_url") else ""
                lines.append(f"- {r['name']} [{r['kind']}{loc}] — {r['detail']}{link}")
            content = "Register matches:\n" + "\n".join(lines)
        else:
            c = registry.register_counts()
            content = (
                f"No entries matched “{query}” in the indexed ESMA registers. "
                "Current register status — a zero is current market status, NOT missing data: "
                f"{c['casps']} authorised CASPs · {c['emt_issuers']} e-money-token issuers · "
                f"{c['art_issuers']} asset-referenced-token issuers authorised under Title III · "
                f"{c['other_whitepapers']} Title II white papers · {c['non_compliant']} flagged entities. "
                "If the user asked about a category that shows 0 (e.g. ART issuers), state plainly that "
                "none have been authorised to date — do not imply the data is missing."
            )
        return {
            "content": content,
            "summary": f"Looked up “{query}” in ESMA register → {len(results)} match(es)",
            "citations": [],
        }

    if name == "check_enforcement":
        entity = (tool_input or {}).get("entity", "").strip()
        rows = registry.check_enforcement(entity) if entity else []
        if rows:
            lines = [
                f"- {r['entity']} — flagged by {r['authority']}"
                + (f" ({r['decision_date']})" if r.get("decision_date") else "")
                + (f": {r['reason']}" if r.get("reason") and r["reason"] != "None" else "")
                for r in rows
            ]
            content = "Enforcement / warning matches:\n" + "\n".join(lines)
        else:
            content = "No enforcement actions or warnings found for that entity in the snapshot."
        return {
            "content": content,
            "summary": f"Checked enforcement for “{entity}” → {len(rows)} record(s)",
            "citations": [],
        }

    return {"content": f"Unknown tool: {name}", "summary": f"Unknown tool {name}", "citations": []}
