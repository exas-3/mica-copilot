"""CLI: build/refresh the news corpus.

    python -m app.news.poll                 # poll all feeds
    python -m app.news.poll --press         # only trade press
    python -m app.news.poll --regulators    # only regulators
"""
from __future__ import annotations

import argparse

from app.config import get_settings
from app.db import close_pool
from app.news.poller import poll


def main() -> None:
    ap = argparse.ArgumentParser(description="Poll RSS feeds → full-text news corpus.")
    ap.add_argument("--press", action="store_true", help="Only poll trade-press feeds.")
    ap.add_argument("--regulators", action="store_true", help="Only poll regulator feeds.")
    args = ap.parse_args()

    types: list[str] = []
    if args.press:
        types.append("press")
    if args.regulators:
        types.append("regulator")

    print(f"→ Embedder: {get_settings().embedder} | store mode: {get_settings().news_store}")
    print(f"→ Polling: {types or 'all feeds'}")
    result = poll(types or None)
    print(f"✓ {result}")
    close_pool()


if __name__ == "__main__":
    main()
