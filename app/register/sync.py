"""Sync the real ESMA MiCA registers into Postgres.

Fetches the 5 public ESMA CSVs, normalises them, (re)creates the register tables, and
bulk-inserts. Caches the parsed rows to data/register_snapshot.json for offline rebuilds.
The `other_whitepapers` table carries `token_name`/`ticker` filled by `whitepapers.py`
(read from the white-paper documents) — applied here from data/wp_tokens.json if present.

    python -m app.register.sync             # load from cached snapshot (offline)
    python -m app.register.sync --refresh   # re-fetch the ESMA CSVs
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import close_pool, get_conn
from app.register import parse
from app.register.sources import DATASETS, USER_AGENT, url

ROOT = Path(__file__).resolve().parents[2]

SCHEMA = """
DROP TABLE IF EXISTS casps, emt_issuers, art_issuers, other_whitepapers, non_compliant CASCADE;

CREATE TABLE casps (
    pk text PRIMARY KEY, competent_authority text, country text, lei_name text, lei text,
    commercial_name text, website text, service_codes text[] DEFAULT '{}', auth_date date, last_update date
);
CREATE TABLE emt_issuers (
    pk text PRIMARY KEY, competent_authority text, country text, lei_name text, lei text,
    commercial_name text, website text, wp_url text, auth_date date
);
CREATE TABLE art_issuers (
    pk text PRIMARY KEY, competent_authority text, country text, lei_name text, lei text,
    commercial_name text, website text, credit_institution text, wp_url text, auth_date date
);
CREATE TABLE other_whitepapers (
    pk text PRIMARY KEY, competent_authority text, country text, lei_name text, lei text,
    lei_name_casp text, offer_countries text[] DEFAULT '{}', dti text, wp_url text,
    wp_comments text, wp_last_update date,
    token_name text, ticker text, extract_confidence text
);
CREATE TABLE non_compliant (
    pk text PRIMARY KEY, competent_authority text, country text, lei_name text, lei text,
    commercial_name text, website text, infringement text, reason text, decision_date date
);
CREATE INDEX other_wp_ticker_idx ON other_whitepapers (lower(ticker));
CREATE INDEX other_wp_token_idx  ON other_whitepapers (lower(token_name));
"""


# ── CSV row → normalised dict (per dataset) ──────────────────────────────────
def _map(dataset: str, r: dict) -> dict | None:
    g = lambda k: parse.clean(r.get(k))  # noqa: E731
    ca, country, lei_name, lei = g("ae_competentAuthority"), g("ae_homeMemberState"), g("ae_lei_name"), g("ae_lei")
    cn = g("ae_commercial_name")

    if dataset == "CASPS":
        if not (cn or lei_name):
            return None
        pk = f"lei::{lei}" if lei else f"name::{cn}::{ca}"
        return {"pk": pk, "competent_authority": ca, "country": country, "lei_name": lei_name, "lei": lei,
                "commercial_name": cn, "website": g("ae_website"),
                "service_codes": parse.service_letters(r.get("ac_serviceCode")),
                "auth_date": parse.parse_date(r.get("ac_authorisationNotificationDate")),
                "last_update": parse.parse_date(r.get("ac_lastupdate"))}

    if dataset in ("EMTWP", "ARTZZ"):
        if not (cn or lei_name):
            return None
        pk = f"lei::{lei}::{cn}" if lei else f"name::{cn}::{ca}"
        base = {"pk": pk, "competent_authority": ca, "country": country, "lei_name": lei_name, "lei": lei,
                "commercial_name": cn, "website": g("ae_website"), "wp_url": g("wp_url"),
                "auth_date": parse.parse_date(r.get("ac_authorisationNotificationDate"))}
        if dataset == "ARTZZ":
            base["credit_institution"] = g("ae_credit_institution")
        return base

    if dataset == "OTHER":
        wp = g("wp_url")
        if not (wp or lei_name):
            return None
        pk = f"lei::{lei}::{wp}" if lei else f"wp::{wp}::{lei_name}"
        return {"pk": pk, "competent_authority": ca, "country": country, "lei_name": lei_name, "lei": lei,
                "lei_name_casp": g("ae_lei_name_casp"), "offer_countries": parse.split_pipe(r.get("ae_offerCode_cou")),
                "dti": g("ae_DTI_FFG"), "wp_url": wp, "wp_comments": g("wp_comments"),
                "wp_last_update": parse.parse_date(r.get("wp_lastupdate")),
                "token_name": None, "ticker": None, "extract_confidence": None}

    if dataset == "NCASP":
        if not (cn or lei_name):
            return None
        pk = f"{lei or 'NOLEI'}::{cn}::{ca}"
        return {"pk": pk, "competent_authority": ca, "country": country, "lei_name": lei_name, "lei": lei,
                "commercial_name": cn, "website": g("ae_website"), "infringement": g("ae_infrigment"),
                "reason": g("ae_reason"), "decision_date": parse.parse_date(r.get("ae_decision_date"))}
    return None


def _fetch(dataset: str) -> list[dict]:
    resp = httpx.get(url(dataset), timeout=90, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.content.decode("utf-8-sig")))
    out, seen = [], set()
    for raw in reader:
        row = _map(dataset, raw)
        if row and row["pk"] not in seen:
            seen.add(row["pk"])
            out.append(row)
    return out


def fetch_all() -> dict[str, list[dict]]:
    data = {}
    for dataset, (_, table) in DATASETS.items():
        try:
            rows = _fetch(dataset)
        except Exception as e:  # noqa: BLE001
            print(f"   ! {dataset} fetch failed: {e}")
            rows = []
        print(f"   {dataset:6} → {len(rows):4} rows ({table})")
        data[table] = rows
    return data


_COLS = {
    "casps": ["pk", "competent_authority", "country", "lei_name", "lei", "commercial_name", "website", "service_codes", "auth_date", "last_update"],
    "emt_issuers": ["pk", "competent_authority", "country", "lei_name", "lei", "commercial_name", "website", "wp_url", "auth_date"],
    "art_issuers": ["pk", "competent_authority", "country", "lei_name", "lei", "commercial_name", "website", "credit_institution", "wp_url", "auth_date"],
    "other_whitepapers": ["pk", "competent_authority", "country", "lei_name", "lei", "lei_name_casp", "offer_countries", "dti", "wp_url", "wp_comments", "wp_last_update", "token_name", "ticker", "extract_confidence"],
    "non_compliant": ["pk", "competent_authority", "country", "lei_name", "lei", "commercial_name", "website", "infringement", "reason", "decision_date"],
}


def load(refresh: bool = False) -> dict[str, int]:
    s = get_settings()
    snap = ROOT / s.register_snapshot_path
    if refresh or not snap.exists():
        print("→ Fetching ESMA register CSVs…")
        data = fetch_all()
        snap.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"   cached → {snap.name}")
    else:
        print(f"→ Loading register from cache ({snap.name})")
        data = json.loads(snap.read_text(encoding="utf-8"))

    # Apply extracted white-paper tokens, if available.
    wp_tokens_path = ROOT / s.wp_tokens_path
    if wp_tokens_path.exists():
        tokens = json.loads(wp_tokens_path.read_text(encoding="utf-8"))
        for row in data.get("other_whitepapers", []):
            t = tokens.get(row["pk"])
            if t:
                row["token_name"], row["ticker"], row["extract_confidence"] = t.get("token_name"), t.get("ticker"), t.get("confidence")

    counts: dict[str, int] = {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            for stmt in [s for s in SCHEMA.split(";") if s.strip()]:
                cur.execute(stmt)
            for table, cols in _COLS.items():
                rows = data.get(table, [])
                if rows:
                    ph = ", ".join(["%s"] * len(cols))
                    cur.executemany(
                        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph}) ON CONFLICT (pk) DO NOTHING",
                        [[row.get(c) for c in cols] for row in rows],
                    )
                counts[table] = len(rows)
        conn.commit()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync the real ESMA MiCA registers.")
    ap.add_argument("--refresh", action="store_true", help="Re-fetch the ESMA CSVs (else use cache).")
    args = ap.parse_args()
    counts = load(refresh=args.refresh)
    print("✓ Registers loaded:", " · ".join(f"{k}={v}" for k, v in counts.items()))
    close_pool()


if __name__ == "__main__":
    main()
