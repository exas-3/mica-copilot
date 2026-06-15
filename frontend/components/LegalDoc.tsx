"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders a legal document (privacy / terms) from a markdown string with readable doc
 *  typography. External links open in a new tab; internal links stay in-app. */
export function LegalDoc({
  title,
  updated,
  eyebrow = "LEGAL",
  children,
}: {
  title: string;
  updated: string;
  eyebrow?: string;
  children: string;
}) {
  return (
    <div className="legal-page">
      <div className="page-header">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p className="muted">Last updated: {updated}</p>
      </div>
      <article className="panel legal md">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node, href, children: c, ...props }: { node?: unknown; href?: string; children?: ReactNode }) => {
              const external = !!href && /^https?:\/\//.test(href);
              const ext = external ? { target: "_blank", rel: "noreferrer noopener" } : {};
              return (
                <a href={href} {...ext} {...props}>
                  {c}
                </a>
              );
            },
          }}
        >
          {children}
        </ReactMarkdown>
      </article>
    </div>
  );
}
