"""Deterministic entity extraction over article text.

Matches a curated watchlist of crypto firms / token symbols (whole-word, case-insensitive
for names; exact for short symbols) so that entity-specific queries — "what's happening
with Binance" — can filter/boost news. Free and deterministic (no LLM call).
"""
from __future__ import annotations

import re

# Firms / brands (names). Whole-word, case-insensitive.
_FIRMS = [
    "Binance", "Coinbase", "Kraken", "Bybit", "OKX", "Crypto.com", "Bitstamp", "Bitpanda",
    "Gemini", "Bitget", "KuCoin", "Gate.io", "MoonPay", "Revolut", "Robinhood", "eToro",
    "Circle", "Tether", "Paxos", "Ripple", "Bitfinex", "BitMEX", "Bitvavo", "Nexo", "Wirex",
    "Consensys", "Société Générale", "SG-Forge", "Quantoz", "Monerium", "StablR", "Schuman",
    "Banking Circle", "AllUnity", "Boerse Stuttgart", "N26", "21X", "Clear Junction",
]
# Token / stablecoin symbols. Exact whole-word (kept >=3 chars, distinctive).
_SYMBOLS = ["USDT", "USDC", "EURC", "EURe", "EURT", "PYUSD", "EURI", "EURCV", "EURQ", "USDQ", "EUROe", "EURAU"]

_FIRM_RES = [(f, re.compile(rf"(?<![\w]){re.escape(f)}(?![\w])", re.IGNORECASE)) for f in _FIRMS]
_SYM_RES = [(s, re.compile(rf"(?<![\w]){re.escape(s)}(?![\w])")) for s in _SYMBOLS]


def extract_entities(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for name, rx in _FIRM_RES:
        if rx.search(text):
            found.append(name)
    for sym, rx in _SYM_RES:
        if rx.search(text):
            found.append(sym)
    # stable de-dup, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for e in found:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out
