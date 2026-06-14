"use client";

import { useState } from "react";
import { classify, ClassifyResult } from "@/lib/api";

const EXAMPLES = [
  "A token pegged 1:1 to the euro, redeemable at par on demand, backed by euro bank deposits and short-term EU government bonds.",
  "A token whose value is stabilised by referencing a basket of USD, gold and Bitcoin.",
  "A platform that lets users swap one crypto-asset for another and holds their assets in custody.",
];

function assetClass(t: string): string {
  if (t.includes("EMT")) return "accent";
  if (t.includes("ART")) return "accent";
  if (t.includes("out of scope")) return "muted";
  if (t.includes("uncertain")) return "warn";
  return "ok";
}

export function Classify() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(desc: string) {
    const d = desc.trim();
    if (!d || busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await classify(d));
    } catch (e: any) {
      setError(e.message || "Classification failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <textarea
          rows={4}
          className="input"
          style={{ width: "100%" }}
          placeholder="Describe the token, stablecoin, or crypto-asset service…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="composer" style={{ marginTop: 12 }}>
          <button className="btn" onClick={() => run(text)} disabled={busy}>
            {busy ? "Classifying…" : "Classify under MiCA"}
          </button>
        </div>
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <span key={ex} className="example" onClick={() => { setText(ex); run(ex); }}>
              {ex.slice(0, 52)}…
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div className="panel">
          <span className="error">{error}</span>
        </div>
      )}

      {result && (
        <div className="panel">
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span className={`badge ${assetClass(result.asset_type)}`}>{result.asset_type}</span>
            <span className="badge muted">confidence: {result.confidence}</span>
          </div>
          <p style={{ marginTop: 12 }}>{result.asset_rationale}</p>

          {result.services.some((s) => s.applies) && (
            <>
              <div className="section-label">Crypto-asset services implied</div>
              <div className="svc-grid">
                {result.services
                  .filter((s) => s.applies)
                  .map((s) => (
                    <div key={s.code} className="svc on">
                      <span className="dot" />
                      <span className="mono">({s.code})</span> {s.name}
                    </div>
                  ))}
              </div>
            </>
          )}

          {result.obligations.length > 0 && (
            <>
              <div className="section-label">Key obligations</div>
              <ul className="oblig">
                {result.obligations.map((o, i) => (
                  <li key={i}>
                    {o.obligation} {o.article_ref && <span className="ref">[{o.article_ref}]</span>}
                  </li>
                ))}
              </ul>
            </>
          )}

          {result.citations.length > 0 && (
            <>
              <div className="section-label">Citations</div>
              {result.citations.map((c, i) => (
                <div key={i} className="cite-card">
                  <a className="cite-ref" href={c.source_url} target="_blank" rel="noreferrer">
                    {c.article_ref} ↗
                  </a>
                  {c.title && <span className="cite-title"> — {c.title}</span>}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
