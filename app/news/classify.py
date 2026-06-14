"""MiCA-relevance triage for news headlines — Haiku 4.5, mirroring the dashboard.

Returns per item: {relevant, mica, region, topic}. Batched (20/call). Falls back to a
keyword heuristic when no ANTHROPIC_API_KEY is set, so the poller still works offline
(it just keeps everything crypto-regulatory by keyword).
"""
from __future__ import annotations

import json
import re

from app.config import get_settings

TOPICS = {"enforcement", "authorisation", "guidance", "legislation", "supervision", "market", "other"}
_EU_EEA = {"EU", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
           "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
           "IS", "LI", "NO"}

_SYSTEM = """You triage news headlines for an EU CRYPTO-ASSET regulation copilot (MiCA).
For each item return an object with:
- "relevant": true ONLY if it is specifically about CRYPTO-ASSETS / digital assets / stablecoins /
  distributed-ledger in a REGULATORY or LEGAL context — MiCA; authorisation/licensing of crypto
  firms (CASPs) or stablecoin (EMT/ART) issuers; crypto enforcement, sanctions, or public warnings;
  crypto-specific supervisory guidance/standards; crypto legislation; or court/legal proceedings
  involving crypto. false for market/price/product/technology/partnership news, AND for general
  financial regulation not specific to crypto. When unsure, false.
- "region": "EU" for MiCA/EU-wide; an ISO-3166 alpha-2 code for a single country; "GLOBAL" for
  international; or null.
- "topic": one of enforcement|authorisation|guidance|legislation|supervision|market|other.
Reply with ONLY a JSON array, no prose:
[{"i":<index>,"relevant":<bool>,"region":<string|null>,"topic":"<...>"}]"""

_CRYPTO_RE = re.compile(r"\b(crypto|crypto-asset|digital asset|stablecoin|bitcoin|ethereum|token|casp|mica|emt|art|defi|web3|ledger|blockchain)\b", re.I)
_REG_RE = re.compile(r"\b(regulat|licen|authoris|authoriz|enforce|sanction|warning|supervis|complian|legal|court|fine|ban|guidelin|standard|esma|eba|bafin|amf|cssf|mfsa|afm)\b", re.I)
_EU_RE = re.compile(r"\b(mica|esma|eba|mifid|bafin|consob|mfsa|cssf|amf|afm|european|\beu\b)\b", re.I)


def _heuristic(item: dict) -> dict:
    text = f"{item.get('title','')} {item.get('summary','')}"
    relevant = bool(_CRYPTO_RE.search(text) and _REG_RE.search(text))
    eu = bool(relevant and _EU_RE.search(text))
    return {"relevant": relevant, "mica": eu, "region": "EU" if eu else None, "topic": None, "method": "heuristic"}


def classify_batch(items: list[dict]) -> list[dict]:
    """items: [{title, summary, source_type}]. Returns aligned [{relevant, mica, region, topic, method}]."""
    s = get_settings()
    if not s.has_claude:
        return [_heuristic(it) for it in items]

    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    out: list[dict] = [None] * len(items)  # type: ignore
    for start in range(0, len(items), 20):
        batch = items[start : start + 20]
        lines = "\n".join(
            f"{i}. {it.get('title','')}" + (f" — {it.get('summary','')}" if it.get("summary") else "")
            for i, it in enumerate(batch)
        )
        try:
            resp = client.messages.create(
                model=s.cheap_model, max_tokens=1500,
                system=_SYSTEM, messages=[{"role": "user", "content": lines}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            arr = json.loads(text[text.index("[") : text.rindex("]") + 1])
            by_i = {int(p.get("i", -1)): p for p in arr if isinstance(p, dict)}
        except Exception:
            by_i = {}
        for j, it in enumerate(batch):
            p = by_i.get(j)
            if not p:
                out[start + j] = _heuristic(it)
                continue
            region = p.get("region")
            region = str(region).upper()[:6] if region else None
            topic = p.get("topic") if p.get("topic") in TOPICS else None
            out[start + j] = {
                "relevant": bool(p.get("relevant")),
                "mica": bool(region in _EU_EEA) if region else False,
                "region": region,
                "topic": topic,
                "method": "ai",
            }
    return out  # type: ignore
