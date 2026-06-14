"""Read each Title II white paper and extract the token it concerns.

ESMA's white-paper register has no token-name field — only an offeror and a `wp_url`. So we
fetch the document (PDF or HTML landing page), have Haiku read it, and record the token
name + ticker. Results are cached to data/wp_tokens.json (incremental, re-runnable) and
written onto `other_whitepapers.token_name`/`ticker`, which the lookup tool then searches.

Processing is batched in three phases so native parsers never run concurrently (lxml/pypdf
are not thread-safe — concurrent parsing segfaults): **fetch concurrently → parse on the main
thread → Haiku concurrently**.

    python -m app.register.whitepapers            # resolve all unresolved white papers
    python -m app.register.whitepapers --limit 50 # cap (testing)
    python -m app.register.whitepapers --recheck  # re-read low-confidence ones
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import close_pool, get_conn
from app.rag.pdf import extract_text

ROOT = Path(__file__).resolve().parents[2]
_UA = {"User-Agent": "mica-copilot/0.2 (+educational; non-commercial)"}
_BATCH = 60

_PROMPT = """You are reading an EU MiCA crypto-asset white paper (or the landing page that links it).
Identify the specific crypto-asset (token) the white paper concerns.

Offeror: {offeror}
URL: {url}

Return ONLY a JSON object: {{"token_name": <full token name or null>, "ticker": <symbol/ticker in UPPERCASE or null>, "issuer": <issuer name or null>, "confidence": "high"|"medium"|"low"}}
Rules: ticker is the trading symbol (e.g. ADA, MEGA, EURC). If the text does not clearly identify a single token, set unknown fields to null and confidence "low". Do not invent a ticker.

Document text:
{text}"""


def _fetch_raw(row: dict) -> tuple[dict, bytes | None, str]:
    url = row.get("wp_url") or ""
    try:
        resp = httpx.get(url if url.startswith("http") else f"https://{url}",
                         timeout=30, follow_redirects=True, headers=_UA)
        resp.raise_for_status()
        return row, resp.content, resp.headers.get("content-type", "")
    except Exception:
        return row, None, ""


def _heuristic(offeror: str, url: str) -> dict:
    name = re.sub(r"\b(GmbH|FlexCo|Ltd|Limited|B\.?V\.?|S\.?A\.?|AG|UG|Inc|LLC|OÜ|Sp\. z o\.o\.|Stiftung|Association|Verein|e\.V\.|Foundation|Network|Sales|Capital|Technology|Technologies|Labs)\b\.?",
                  "", offeror or "", flags=re.I).strip(" .-,")
    return {"token_name": name or None, "ticker": None, "issuer": offeror or None, "confidence": "none"}


def _haiku(client, model: str, row: dict, text: str | None) -> dict:
    offeror = row.get("lei_name") or row.get("lei_name_casp") or ""
    if not text or len(text) < 200:
        return {"pk": row["pk"], **_heuristic(offeror, row.get("wp_url") or "")}
    try:
        resp = client.messages.create(
            model=model, max_tokens=200,
            messages=[{"role": "user", "content": _PROMPT.format(offeror=offeror, url=row.get("wp_url"), text=text[:5000])}],
        )
        out = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        data = json.loads(out[out.index("{"): out.rindex("}") + 1])
        tk = (data.get("ticker") or "").strip().upper() or None
        return {"pk": row["pk"], "token_name": data.get("token_name") or None,
                "ticker": tk, "issuer": data.get("issuer"), "confidence": data.get("confidence") or "low"}
    except Exception:
        return {"pk": row["pk"], **_heuristic(offeror, row.get("wp_url") or "")}


def _save(cache: dict, cache_path: Path, updates: list[dict]) -> None:
    for u in updates:
        cache[u["pk"]] = {k: u.get(k) for k in ("token_name", "ticker", "issuer", "confidence")}
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE other_whitepapers SET token_name=%s, ticker=%s, extract_confidence=%s WHERE pk=%s",
                [[u.get("token_name"), u.get("ticker"), u.get("confidence"), u["pk"]] for u in updates],
            )
        conn.commit()


def run(limit: int | None = None, recheck: bool = False) -> dict:
    s = get_settings()
    if not s.has_claude:
        raise SystemExit("ANTHROPIC_API_KEY not set — white-paper extraction needs Haiku.")
    import anthropic

    cache_path = ROOT / s.wp_tokens_path
    cache: dict = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    with get_conn() as conn:
        rows = [dict(zip(["pk", "wp_url", "lei_name", "lei_name_casp"], r)) for r in conn.execute(
            "SELECT pk, wp_url, lei_name, lei_name_casp FROM other_whitepapers ORDER BY pk").fetchall()]

    def needs(pk: str) -> bool:
        return pk not in cache or (recheck and cache[pk].get("confidence") in ("low", "none"))

    todo = [r for r in rows if needs(r["pk"])]
    if limit:
        todo = todo[:limit]
    print(f"→ {len(rows)} white papers; resolving {len(todo)} (cached {len(rows) - len(todo)})…")

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    done = 0
    workers = s.wp_extract_workers
    for i in range(0, len(todo), _BATCH):
        batch = todo[i: i + _BATCH]
        # Phase 1 — concurrent fetch (httpx is thread-safe).
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fetched = list(ex.map(_fetch_raw, batch))
        # Phase 2 — parse on the MAIN thread only (lxml/pypdf are not thread-safe).
        parsed = []
        for row, content, ct in fetched:
            text = None
            if content:
                try:
                    text = extract_text(content, ct, row.get("wp_url") or "")
                except Exception:
                    text = None
            parsed.append((row, text))
        # Phase 3 — concurrent Haiku (no native code).
        with ThreadPoolExecutor(max_workers=workers) as ex:
            updates = list(ex.map(lambda rt: _haiku(client, s.cheap_model, rt[0], rt[1]), parsed))
        _save(cache, cache_path, updates)
        done += len(batch)
        print(f"   …{done}/{len(todo)}")

    resolved = sum(1 for v in cache.values() if v.get("ticker"))
    named = sum(1 for v in cache.values() if v.get("token_name"))
    print(f"✓ tickers resolved: {resolved}/{len(rows)} · named: {named}/{len(rows)} → {cache_path.name}")
    return {"total": len(rows), "tickers": resolved, "named": named}


def main() -> None:
    ap = argparse.ArgumentParser(description="Read white papers → token name/ticker.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--recheck", action="store_true", help="Re-read low-confidence entries.")
    args = ap.parse_args()
    run(limit=args.limit, recheck=args.recheck)
    close_pool()


if __name__ == "__main__":
    main()
