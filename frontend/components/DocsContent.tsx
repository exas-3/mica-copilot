"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Map the repo's inter-doc markdown links to the in-app /docs routes.
const SLUG_BY_FILE: Record<string, string> = {
  "DOCUMENTATION.md": "documentation",
  "METHODOLOGY.md": "methodology",
  "DATA-SOURCES.md": "data-sources",
  "EXAMPLES.md": "examples",
  "README.md": "documentation",
};

/** GitHub-style heading slug so in-doc `#section` links resolve to the rendered headings. */
function slugify(s: string): string {
  return s.toLowerCase().replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");
}

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in node)
    return textOf((node as { props: { children?: ReactNode } }).props.children);
  return "";
}

function rewriteHref(href?: string): { href: string; external: boolean } {
  if (!href) return { href: "#", external: false };
  if (/^https?:\/\//.test(href)) return { href, external: true };
  if (href.startsWith("#")) return { href, external: false };
  const [pathPart, frag] = href.split("#");
  const base = pathPart.split("/").pop() || "";
  if (base.toLowerCase().endsWith(".md")) {
    const slug = SLUG_BY_FILE[base] ?? "documentation";
    return { href: `/docs/${slug}${frag ? "#" + frag : ""}`, external: false };
  }
  return { href, external: false };
}

function rewriteImg(src?: string): string {
  if (!src) return "";
  if (/^https?:\/\//.test(src)) return src;
  return "/docs-assets/" + src.replace(/^\.?\//, "");
}

const heading =
  (Tag: "h1" | "h2" | "h3" | "h4") =>
  ({ children }: { children?: ReactNode }) => {
    const id = slugify(textOf(children));
    return <Tag id={id}>{children}</Tag>;
  };

export function DocsContent({ content }: { content: string }) {
  return (
    <article className="md docs-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, href, children, ...props }) => {
            const r = rewriteHref(href);
            const ext = r.external ? { target: "_blank", rel: "noopener noreferrer" } : {};
            return (
              <a href={r.href} {...ext} {...props}>
                {children}
              </a>
            );
          },
          // eslint-disable-next-line @next/next/no-img-element
          img: ({ node, src, alt, ...props }) => (
            <img
              src={rewriteImg(typeof src === "string" ? src : "")}
              alt={alt || "MiCA Copilot documentation screenshot"}
              loading="lazy"
              decoding="async"
              {...props}
            />
          ),
          h1: heading("h1"),
          h2: heading("h2"),
          h3: heading("h3"),
          h4: heading("h4"),
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  );
}
