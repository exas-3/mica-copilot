"""Evaluation harness for the MiCA copilot.

Measures, against a small golden set (eval/goldens.jsonl):
  - retrieval hit@k  — does the expected article appear in the retrieved provisions?
  - citation hit     — (e2e) does the agent's answer actually cite the expected article?
  - abstention       — (e2e) does the agent decline on out-of-corpus questions?
  - faithfulness     — (judge) is the answer supported by the retrieved context? (LLM-as-judge)

Run:
  python -m eval.run                 # retrieval-only (offline; needs DB + embedder, no Claude key)
  python -m eval.run --e2e           # also run the full agent loop and score citations/abstention
  python -m eval.run --e2e --judge   # also score faithfulness with an LLM judge (Haiku)

Writes eval/results/scorecard.json.
"""
from __future__ import annotations

import argparse
import json
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


def retrieval_hit(g: dict) -> bool:
    if g["kind"] != "answerable":
        return True  # not applicable
    got = _refs(rag.retrieve_for_answer(g["question"]))
    return any(exp in got for exp in g["expected_articles"])


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true", help="Run the full agent loop and score citations/abstention.")
    ap.add_argument("--judge", action="store_true", help="Score faithfulness with an LLM judge (implies --e2e).")
    args = ap.parse_args()
    if args.judge:
        args.e2e = True

    goldens = load_goldens()
    answerable = [g for g in goldens if g["kind"] == "answerable"]
    abstainers = [g for g in goldens if g["kind"] == "abstain"]

    rows = []
    retr_hits = 0
    cite_hits = 0
    abstain_ok = 0
    faithful_ok = 0
    judged = 0

    if args.e2e:
        from app.services import llm

    for g in goldens:
        row = {"question": g["question"], "kind": g["kind"]}

        if g["kind"] == "answerable":
            r_hit = retrieval_hit(g)
            retr_hits += int(r_hit)
            row["retrieval_hit"] = r_hit

        if args.e2e:
            result = llm.chat_sync(g["question"], [])
            cited = {(c.get("article_ref") or "").split("(")[0].strip() for c in result.get("citations", [])}
            if g["kind"] == "answerable":
                c_hit = any(exp in cited for exp in g["expected_articles"])
                cite_hits += int(c_hit)
                row["citation_hit"] = c_hit
                if args.judge and result.get("citations"):
                    ctx = rag.build_context(rag.retrieve_for_answer(g["question"]))
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

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "scorecard.json").write_text(json.dumps({"scorecard": scorecard, "rows": rows}, indent=2))

    print("\n=== MiCA Copilot — Evaluation Scorecard ===")
    for k, v in scorecard.items():
        print(f"  {k:24s}: {v}")
    print(f"\n  (details written to eval/results/scorecard.json)")
    print("  embedder:", get_settings().embedder)


if __name__ == "__main__":
    main()
