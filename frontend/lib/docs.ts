import fs from "node:fs";
import path from "node:path";

export type DocMeta = { slug: string; title: string; file: string; blurb: string };

/** The docs surfaced in the /docs UI, in sidebar order. Sourced from the repo's docs/ folder. */
export const DOCS: DocMeta[] = [
  { slug: "documentation", title: "Documentation", file: "DOCUMENTATION.md", blurb: "Overview, architecture, API & UI" },
  { slug: "methodology", title: "Methodology", file: "METHODOLOGY.md", blurb: "RAG pipeline, retrieval & evaluation" },
  { slug: "data-sources", title: "Data Sources", file: "DATA-SOURCES.md", blurb: "Corpora, ESMA registers, news, refresh" },
  { slug: "examples", title: "Examples", file: "EXAMPLES.md", blurb: "Endpoint requests, SSE protocol, UI flows" },
];

/** Locate the repo docs/ folder. `next` runs with cwd = frontend/, so ../docs is the repo docs. */
function docsDir(): string {
  const candidates = [
    path.resolve(process.cwd(), "..", "docs"),
    path.resolve(process.cwd(), "docs"),
  ];
  return candidates.find((c) => fs.existsSync(c)) ?? candidates[0];
}

export function getDoc(slug: string): { meta: DocMeta; content: string } | null {
  const meta = DOCS.find((d) => d.slug === slug);
  if (!meta) return null;
  try {
    return { meta, content: fs.readFileSync(path.join(docsDir(), meta.file), "utf-8") };
  } catch {
    return null;
  }
}
