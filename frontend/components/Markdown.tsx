"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders the assistant's markdown answer (bold, bullet/numbered lists, tables, code,
 *  links) as formatted HTML instead of raw markdown text. Links open in a new tab.
 *  Inline `[Article 36]` references stay as visible bracket text (not markdown links). */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
