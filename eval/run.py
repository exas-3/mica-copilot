"""Evaluation harness for the MiCA copilot.

Measures, against a golden set (eval/goldens.jsonl):
  - retrieval hit@k  — does the expected article appear in the retrieved provisions?
  - citation hit     — (e2e) does the agent's answer actually cite the expected article?
  - abstention       — (e2e) does the agent decline on out-of-corpus questions?
  - faithfulness     — (judge) is the answer supported by the retrieved context? (LLM-as-judge)
  - register hit     — (kind="register") does the ESMA-register lookup find the expected entity?

Run:
  python -m eval.run                 # retrieval-only (offline; needs DB + embedder, no Claude key)
  python -m eval.run --ablate        # retrieval-only lever ablation (prefix / hybrid / rerank), no key
  python -m eval.run --e2e           # also run the full agent loop and score citations/abstention
  python -m eval.run --e2e --judge   # also score faithfulness with an LLM judge (Haiku)
  python -m eval.run --e2e --judge --tag after --baseline eval/results/scorecard_before.json

Writes eval/results/scorecard.json (and scorecard_<tag>.json when --tag is given).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.config import get_settings
from app.services import rag

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "eval" / "goldens.jsonl"
RESULTS = ROOT / "eval" / "results"


def load_goldens() -> list[dict]:
    return [json.loads(l) for l in GOLDENS.read_text(encoding="utf-8").splitlines() if l.strip()]


def _refs(chunks: list[dict]) -> set[str]:
    return {(c.get("article_ref") or "").split("(")[0].strip() for c in chunks}


def _match(g: dict, raw_refs: list[str]) -> bool:
    """A hit if an expected article appears among the refs, OR the topic's accepted Level-2
    elaboration does (the golden's optional ``also_accept`` substrings) — since the specific
    RTS/guideline that elaborates the article is itself a correct answer."""
    stripped = {r.split("(")[0].strip() for r in raw_refs}
    if any(exp in stripped for exp in g["expected_articles"]):
        return True
    return any(a.lower() in r.lower() for a in (g.get("also_accept") or []) for r in raw_refs)


def retrieval_hit(g: dict) -> bool:
    if g["kind"] != "answerable":
        return True  # not applicable
    raw = [(c.get("article_ref") or "") for c in rag.retrieve_for_answer(g["question"])]
    return _match(g, raw)


def _chunks_for_refs(refs: list[str]) -> list[dict]:
    """Fetch the reg_chunks for specific article references, so the faithfulness judge sees the
    exact provisions the answer *cited* — not just generic top-k retrieval for the question."""
    from app.db import get_conn

    wanted = sorted({r.strip() for r in refs if r and r.strip()})
    if not wanted:
        return []
    out: list[dict] = []
    try:
        with get_conn() as conn:
            for ref in wanted:
                base = ref.split("(")[0].strip()
                rows = conn.execute(
                    "SELECT article_ref, title, chunk_text, source_url FROM reg_chunks "
                    "WHERE article_ref = %s OR article_ref = %s OR article_ref ILIKE %s "
                    "ORDER BY chunk_index LIMIT 3",
                    (ref, base, base + "(%"),
                ).fetchall()
                out += [{"article_ref": r[0], "title": r[1], "chunk_text": r[2], "source_url": r[3]} for r in rows]
    except Exception:  # noqa: BLE001 — judge context is best-effort
        pass
    return out


def judge_context(question: str, cited_refs: list[str] | None = None, k: int = 12) -> str:
    """Build a *generous* context for the faithfulness judge — more chunks than the answer
    pipeline hands the model. Faithfulness asks 'is the answer grounded in the corpus?', so the
    judge should see the relevant provisions in full. We combine top-k retrieval for the question
    with the exact chunks the answer *cited* (so a correctly-cited provision that ranks below the
    top-k is not unfairly judged 'unsupported').
    """
    from app.rag.embed import get_embedder
    from app.rag.store import search_hybrid

    vec = get_embedder().embed_query(question)
    chunks = search_hybrid(question, vec, k)
    if cited_refs:
        have = {c.get("article_ref") for c in chunks}
        for c in _chunks_for_refs(cited_refs):
            if c["article_ref"] not in have:
                chunks.append(c)
                have.add(c["article_ref"])
    return rag.build_context(chunks)


def judge_faithfulness(question: str, answer: str, context: str) -> bool:
    import anthropic

    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    prompt = (
        "You are a strict fact-checker. Given a QUESTION, a CONTEXT of regulation excerpts, and an "
        "ANSWER, decide whether every substantive claim in the ANSWER is supported by the CONTEXT. "
        "Reply with exactly one word: SUPPORTED or UNSUPPORTED.\n\n"
        f"QUESTION: {question}\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
    )
    resp = client.messages.create(
        model=s.cheap_model, max_tokens=8, messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").upper()
    return "UNSUPPORTED" not in text


# ── Ablation (retrieval-only; no Claude key) ─────────────────────────────────
def _clear_caches() -> None:
    """Rebuild the cached singletons that depend on settings (so env overrides take effect)."""
    get_settings.cache_clear()
    from app.rag.embed import get_embedder

    get_embedder.cache_clear()
    try:
        from app.rag.rerank import get_reranker

        get_reranker.cache_clear()
    except Exception:
        pass


def _apply(env: dict) -> None:
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(v)
    _clear_caches()


_ABLATION = [
    ("vector, no query-prefix (baseline)", {"LOCAL_QUERY_PREFIX": "none", "RETRIEVAL_MODE": "vector", "RERANK": "off", "RETRIEVAL_DIVERSITY": "false"}),
    ("+ mxbai query prefix",               {"LOCAL_QUERY_PREFIX": None,   "RETRIEVAL_MODE": "vector", "RERANK": "off", "RETRIEVAL_DIVERSITY": "false"}),
    ("+ hybrid (vector+lexical RRF)",      {"LOCAL_QUERY_PREFIX": None,   "RETRIEVAL_MODE": "hybrid", "RERANK": "off", "RETRIEVAL_DIVERSITY": "false"}),
    ("+ diversity (reserve base + cap)",   {"LOCAL_QUERY_PREFIX": None,   "RETRIEVAL_MODE": "hybrid", "RERANK": "off", "RETRIEVAL_DIVERSITY": "true"}),
]


def ablate(goldens: list[dict]) -> None:
    answerable = [g for g in goldens if g["kind"] == "answerable"]
    n = max(len(answerable), 1)
    print(f"\n=== Retrieval ablation — retrieval_hit@k on {len(answerable)} answerable goldens ===")
    grids: list[tuple[str, float, list[bool]]] = []
    for label, env in _ABLATION:
        _apply(env)
        hits = [_match(g, [(c.get("article_ref") or "") for c in rag.retrieve_for_answer(g["question"])]) for g in answerable]
        grids.append((label, sum(hits) / n, hits))
        print(f"  {label:38s} {sum(hits) / n:.3f}  ({sum(hits)}/{len(answerable)})")

    print("\n  per-question flip grid (columns S0..S{} = ablation stages above):".format(len(_ABLATION) - 1))
    print(f"    {'expected article(s)':<26} " + "  ".join(f"S{i}" for i in range(len(_ABLATION))))
    for j, g in enumerate(answerable):
        marks = "  ".join(" ✓" if grids[s][2][j] else " ✗" for s in range(len(_ABLATION)))
        print(f"    {','.join(g['expected_articles'])[:25]:<26} {marks}")
    _apply({"LOCAL_QUERY_PREFIX": None, "RETRIEVAL_MODE": None, "RERANK": None})  # reset to .env defaults


def _diff(baseline_path: str, scorecard: dict) -> None:
    try:
        base = json.loads(Path(baseline_path).read_text())["scorecard"]
    except Exception as e:  # noqa: BLE001
        print(f"  (could not read baseline {baseline_path}: {e})")
        return
    print("\n  Δ vs baseline:")
    for k, v in scorecard.items():
        if isinstance(v, (int, float)) and isinstance(base.get(k), (int, float)):
            d = v - base[k]
            print(f"    {k:24s}: {base[k]:.3f} → {v:.3f}  ({d:+.3f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true", help="Run the full agent loop and score citations/abstention.")
    ap.add_argument("--judge", action="store_true", help="Score faithfulness with an LLM judge (implies --e2e).")
    ap.add_argument("--ablate", action="store_true", help="Retrieval-only lever ablation (no Claude key). Standalone.")
    ap.add_argument("--tag", default=None, help="Also write eval/results/scorecard_<tag>.json.")
    ap.add_argument("--baseline", default=None, help="Print metric deltas vs a prior scorecard JSON.")
    args = ap.parse_args()
    if args.judge:
        args.e2e = True

    goldens = load_goldens()

    if args.ablate:
        ablate(goldens)
        return

    answerable = [g for g in goldens if g["kind"] == "answerable"]
    abstainers = [g for g in goldens if g["kind"] == "abstain"]
    registers = [g for g in goldens if g["kind"] == "register"]

    rows = []
    retr_hits = cite_hits = abstain_ok = faithful_ok = judged = reg_hits = 0
    usage_totals: dict[str, int] = {}
    usage_n = 0

    if args.e2e:
        from app.services import llm
    if registers:
        from app.services import registry

    for g in goldens:
        row = {"question": g["question"], "kind": g["kind"]}

        if g["kind"] == "answerable":
            r_hit = retrieval_hit(g)
            retr_hits += int(r_hit)
            row["retrieval_hit"] = r_hit

        if g["kind"] == "register":
            # Deterministic ESMA-register lookup (no Claude): does the query find the entity?
            got = registry.search_registry(g.get("query", g["question"]))
            names = " ".join((r.get("name") or "") + " " + (r.get("detail") or "") for r in got).lower()
            ok = bool(got) and all(e.lower() in names for e in g.get("expect_contains", []))
            reg_hits += int(ok)
            row["register_hit"] = ok
            continue

        if args.e2e:
            result = llm.chat_sync(g["question"], [], log=False)  # don't pollute chat_logs with eval
            u = result.get("usage") or {}
            if u:
                for k, v in u.items():
                    usage_totals[k] = usage_totals.get(k, 0) + (v or 0)
                usage_n += 1
                row["model"] = result.get("model")
                row["usage"] = u
            cited_raw = [(c.get("article_ref") or "") for c in result.get("citations", [])]
            if g["kind"] == "answerable":
                c_hit = _match(g, cited_raw)
                cite_hits += int(c_hit)
                row["citation_hit"] = c_hit
                if args.judge and result.get("citations"):
                    ctx = judge_context(g["question"], cited_refs=cited_raw)
                    f = judge_faithfulness(g["question"], result["answer"], ctx)
                    faithful_ok += int(f)
                    judged += 1
                    row["faithful"] = f
            else:  # abstain case: success = no/empty citations OR explicit non-grounded
                did_abstain = (not result.get("grounded")) or len(result.get("citations", [])) == 0
                abstain_ok += int(did_abstain)
                row["abstained"] = did_abstain

        rows.append(row)

    n_ans = max(len(answerable), 1)
    scorecard = {
        "n_total": len(goldens),
        "retrieval_hit@k": round(retr_hits / n_ans, 3),
    }
    if args.e2e:
        scorecard["citation_hit"] = round(cite_hits / n_ans, 3)
        scorecard["abstention_accuracy"] = round(abstain_ok / max(len(abstainers), 1), 3)
        if judged:
            scorecard["faithfulness"] = round(faithful_ok / judged, 3)
    if registers:
        scorecard["register_hit"] = round(reg_hits / max(len(registers), 1), 3)
    if usage_n:
        inp = usage_totals.get("input_tokens", 0)
        out = usage_totals.get("output_tokens", 0)
        cread = usage_totals.get("cache_read_input_tokens", 0)
        ccreate = usage_totals.get("cache_creation_input_tokens", 0)
        total = inp + out
        scorecard["usage"] = {
            "queries_measured": usage_n,
            "avg_input_tokens": round(inp / usage_n, 1),
            "avg_output_tokens": round(out / usage_n, 1),
            "avg_total_tokens": round(total / usage_n, 1),
            "output_share": round(out / total, 3) if total else 0.0,
            # cache-read ratio over (cache_read + fresh input) — confirms the prefix cache hits.
            "cache_read_ratio": round(cread / (cread + inp), 3) if (cread + inp) else 0.0,
            "cache_creation_tokens": ccreate,
        }

    RESULTS.mkdir(exist_ok=True)
    payload = json.dumps({"scorecard": scorecard, "rows": rows}, indent=2)
    (RESULTS / "scorecard.json").write_text(payload)
    if args.tag:
        (RESULTS / f"scorecard_{args.tag}.json").write_text(payload)

    print("\n=== MiCA Copilot — Evaluation Scorecard ===")
    for k, v in scorecard.items():
        if isinstance(v, dict):
            continue
        print(f"  {k:24s}: {v}")
    if "usage" in scorecard:
        u = scorecard["usage"]
        print(f"  {'tokens/query (in→out)':24s}: {u['avg_input_tokens']:.0f} → {u['avg_output_tokens']:.0f} "
              f"(total {u['avg_total_tokens']:.0f}, output share {u['output_share']:.0%})")
        print(f"  {'cache-read ratio':24s}: {u['cache_read_ratio']:.0%}  (n={u['queries_measured']})")
    s = get_settings()
    print(f"\n  config: embedder={s.embedder} retrieval_mode={s.retrieval_mode} rerank={s.rerank} "
          f"effort={s.agent_effort} max_tokens={s.chat_max_tokens} query_routing={s.query_routing}")
    if args.baseline:
        _diff(args.baseline, scorecard)
    print("  (details written to eval/results/scorecard.json)")


if __name__ == "__main__":
    main()
