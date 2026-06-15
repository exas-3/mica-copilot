import { notFound } from "next/navigation";
import { DOCS, getDoc } from "@/lib/docs";
import { DocsContent } from "@/components/DocsContent";

export function generateStaticParams() {
  return [{ slug: [] as string[] }, ...DOCS.map((d) => ({ slug: [d.slug] }))];
}

export default async function DocPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await params;
  const which = slug?.[0] ?? DOCS[0].slug;
  const doc = getDoc(which);
  if (!doc) notFound();
  return <DocsContent content={doc.content} />;
}
