"""RSS feed seed list — mirrored from the sibling mica-dashboard (lib/news/sources.js).

10 official regulators (firm-wide feeds, filtered to MiCA relevance downstream) + 4 crypto
trade-press outlets. URLs validated in the dashboard's production poller.
"""
from __future__ import annotations

SEED_SOURCES: list[dict] = [
    # ── Official regulators ──────────────────────────────────────────────────
    {"name": "ESMA", "type": "regulator", "country": None,
     "rss_url": "https://www.esma.europa.eu/rss.xml"},
    {"name": "EBA", "type": "regulator", "country": None,
     "rss_url": "https://www.eba.europa.eu/rss.xml"},
    {"name": "European Commission (Finance)", "type": "regulator", "country": None,
     "rss_url": "https://finance.ec.europa.eu/node/1408/rss_en"},
    {"name": "BaFin", "type": "regulator", "country": "DE",
     "rss_url": "https://www.bafin.de/EN/service/rss/_function/rssnewsfeed.xml?nn=187494"},
    {"name": "BaFin — Measures", "type": "regulator", "country": "DE",
     "rss_url": "https://www.bafin.de/EN/service/rss/_function/RSS_Massnahmen.xml?nn=187494"},
    {"name": "AMF", "type": "regulator", "country": "FR",
     "rss_url": "https://www.amf-france.org/en/flux-rss/display/30"},
    {"name": "AMF — Warnings", "type": "regulator", "country": "FR",
     "rss_url": "https://www.amf-france.org/en/flux-rss/display/28"},
    {"name": "MFSA", "type": "regulator", "country": "MT",
     "rss_url": "https://www.mfsa.mt/feed/"},
    {"name": "CSSF", "type": "regulator", "country": "LU",
     "rss_url": "https://www.cssf.lu/en/feed/"},
    {"name": "AFM", "type": "regulator", "country": "NL",
     "rss_url": "https://www.afm.nl/en/rss"},
    # ── Crypto trade press ───────────────────────────────────────────────────
    {"name": "CoinDesk", "type": "press", "country": None,
     "rss_url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Cointelegraph", "type": "press", "country": None,
     "rss_url": "https://cointelegraph.com/rss"},
    {"name": "The Block", "type": "press", "country": None,
     "rss_url": "https://www.theblock.co/rss.xml"},
    {"name": "Decrypt", "type": "press", "country": None,
     "rss_url": "https://decrypt.co/feed"},
]

USER_AGENT = "MiCA-Copilot/0.2 (+educational news aggregator; non-commercial)"


def sources_for(types: list[str] | None = None) -> list[dict]:
    if not types:
        return SEED_SOURCES
    return [s for s in SEED_SOURCES if s["type"] in types]
