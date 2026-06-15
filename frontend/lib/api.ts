// Thin client for the FastAPI backend: SSE chat stream, sync chat, classify, registry.

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Citation = {
  kind?: string; // "document" | "news"
  article_ref: string;
  title: string;
  source: string;
  doc_type?: string;
  source_name?: string;
  published_at?: string;
  source_url: string;
  snippet: string;
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type StreamHandlers = {
  onToken: (text: string) => void;
  onTool: (tool: string, summary: string) => void;
  onReset: () => void;
  onThought: (text: string) => void;
  onCitations: (citations: Citation[], grounded: boolean) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function streamChat(
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
      signal,
    });
  } catch (e) {
    handlers.onError(`Could not reach the backend at ${API_URL}. Is it running?`);
    return;
  }
  if (!res.ok || !res.body) {
    if (res.status === 429) {
      const detail = await res.json().catch(() => ({} as any));
      handlers.onError(detail.detail || "Rate limit exceeded — too many requests. Please slow down and try again shortly.");
      return;
    }
    handlers.onError(`Backend error (${res.status}).`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      let evt: any;
      try {
        evt = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      switch (evt.type) {
        case "token":
          handlers.onToken(evt.text);
          break;
        case "tool":
          handlers.onTool(evt.tool, evt.summary);
          break;
        case "reset":
          handlers.onReset();
          break;
        case "thought":
          handlers.onThought(evt.text);
          break;
        case "citations":
          handlers.onCitations(evt.citations ?? [], evt.grounded ?? true);
          break;
        case "done":
          handlers.onDone();
          return;
        case "error":
          handlers.onError(evt.message ?? "Unknown error");
          return;
      }
    }
  }
  handlers.onDone();
}

export type ClassifyResult = {
  asset_type: string;
  asset_rationale: string;
  services: { code: string; name: string; applies: boolean }[];
  obligations: { obligation: string; article_ref: string }[];
  citations: Citation[];
  confidence: string;
};

export async function classify(description: string): Promise<ClassifyResult> {
  const res = await fetch(`${API_URL}/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Classification failed (${res.status}).`);
  }
  return res.json();
}
