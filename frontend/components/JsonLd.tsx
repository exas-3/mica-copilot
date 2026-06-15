// Injects a JSON-LD structured-data block. Render from a SERVER component (layout/page) so the
// markup is in the initial HTML for crawlers — NOT from a "use client" component and NOT via
// generateMetadata (which cannot carry script tags).
export function JsonLd({ data }: { data: Record<string, unknown> | Record<string, unknown>[] }) {
  return (
    <script
      type="application/ld+json"
      // schema objects are app-authored (no user input) → safe to inline.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
