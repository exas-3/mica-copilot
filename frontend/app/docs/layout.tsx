import type { Metadata } from "next";
import { DOCS } from "@/lib/docs";
import { DocsSidebar } from "@/components/DocsSidebar";

export const metadata: Metadata = {
  title: "Documentation — Architecture, Data Sources & Methodology",
  description:
    "Technical documentation for the MiCA Compliance Copilot: architecture, the RAG pipeline and retrieval, data sources, evaluation methodology, and usage examples.",
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const items = DOCS.map(({ slug, title, blurb }) => ({ slug, title, blurb }));
  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">REFERENCE</div>
        <h1>Docs</h1>
        <p className="muted">
          Architecture, methodology, data sources and usage examples for the MiCA Copilot —
          rendered from the project documentation.
        </p>
      </div>
      <div className="docs-grid">
        <aside className="panel docs-aside">
          <DocsSidebar docs={items} />
        </aside>
        <article className="panel docs-content">{children}</article>
      </div>
    </div>
  );
}
