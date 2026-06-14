"use client";

import { useRef, useState } from "react";
import { Citation, ChatMessage, streamChat } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string; tools: string[]; streaming?: boolean };

const EXAMPLES = [
  "What are the reserve requirements for an asset-referenced token issuer?",
  "Who may issue an e-money token, and is it redeemable at par?",
  "What must a CASP do to safekeep clients' crypto-assets?",
  "Is Circle authorised to issue an e-money token in the EU?",
];

export function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [grounded, setGrounded] = useState(true);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function updateLast(fn: (m: Msg) => Msg) {
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = fn(next[next.length - 1]);
      return next;
    });
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setCitations([]);
    setGrounded(true);

    const history: ChatMessage[] = messages
      .filter((m) => !m.streaming)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: q, tools: [] },
      { role: "assistant", content: "", tools: [], streaming: true },
    ]);
    setInput("");

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    await streamChat(
      q,
      history,
      {
        onToken: (t) => updateLast((m) => ({ ...m, content: m.content + t })),
        onTool: (_tool, summary) => updateLast((m) => ({ ...m, tools: [...m.tools, summary] })),
        onReset: () => updateLast((m) => ({ ...m, content: "" })),
        onThought: (t) =>
          updateLast((m) => ({ ...m, tools: [...m.tools, `💭 ${t.length > 140 ? t.slice(0, 140) + "…" : t}`] })),
        onCitations: (c, g) => {
          setCitations(c);
          setGrounded(g);
        },
        onDone: () => {
          updateLast((m) => ({ ...m, streaming: false }));
          setBusy(false);
        },
        onError: (msg) => {
          updateLast((m) => ({ ...m, content: m.content + `\n\n⚠️ ${msg}`, streaming: false }));
          setBusy(false);
        },
      },
      ctrl.signal,
    );
  }

  return (
    <div className="chat-grid">
      <div>
        <div className="panel">
          <div className="messages">
            {messages.length === 0 && (
              <p className="muted">
                Ask a question about the EU Markets in Crypto-Assets Regulation. Answers are
                grounded in the indexed regulation text and cited by article.
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{ display: "contents" }}>
                {m.tools.map((t, j) => (
                  <div key={`t${i}-${j}`} className="tool-chip">⚙ {t}</div>
                ))}
                {(m.content || m.role === "user") && (
                  <div className={`bubble ${m.role}${m.streaming ? " streaming" : ""}`}>{m.content}</div>
                )}
              </div>
            ))}
          </div>

          <div className="composer">
            <input
              value={input}
              placeholder="Ask about MiCA…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              disabled={busy}
            />
            <button className="btn" onClick={() => send(input)} disabled={busy}>
              {busy ? "…" : "Ask"}
            </button>
          </div>

          {messages.length === 0 && (
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <span key={ex} className="example" onClick={() => send(ex)}>
                  {ex}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <aside className="panel">
        <div className="eyebrow">Citations</div>
        <div className="spacer" />
        {!grounded && citations.length === 0 && (
          <span className="badge warn">No grounding — answer withheld</span>
        )}
        {citations.length === 0 && grounded && (
          <p className="muted">Documents and news cited by the answer appear here.</p>
        )}

        {citations.filter((c) => c.kind !== "news").length > 0 && (
          <>
            <div className="section-label">Regulation &amp; documents</div>
            {citations
              .filter((c) => c.kind !== "news")
              .map((c, i) => (
                <div key={`d${i}`} className="cite-card">
                  <a className="cite-ref" href={c.source_url} target="_blank" rel="noreferrer">
                    {c.article_ref || c.title} ↗
                  </a>
                  {c.doc_type && <span className="badge muted" style={{ marginLeft: 8 }}>{c.doc_type}</span>}
                  {c.title && c.article_ref && <div className="cite-title">{c.title}</div>}
                  {c.snippet && <div className="cite-snip">{c.snippet}</div>}
                </div>
              ))}
          </>
        )}

        {citations.filter((c) => c.kind === "news").length > 0 && (
          <>
            <div className="section-label">News</div>
            {citations
              .filter((c) => c.kind === "news")
              .map((c, i) => (
                <div key={`n${i}`} className="cite-card">
                  <a className="cite-ref" href={c.source_url} target="_blank" rel="noreferrer">
                    {c.source_name || "source"} ↗
                  </a>
                  {c.published_at && (
                    <span className="badge muted" style={{ marginLeft: 8 }}>{c.published_at}</span>
                  )}
                  {c.title && <div className="cite-title">{c.title}</div>}
                  {c.snippet && <div className="cite-snip">{c.snippet}</div>}
                </div>
              ))}
          </>
        )}
      </aside>
    </div>
  );
}
