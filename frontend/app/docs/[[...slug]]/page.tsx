import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DOCS, getDoc } from "@/lib/docs";
import { DocsContent } from "@/components/DocsContent";
import { JsonLd } from "@/components/JsonLd";
import { SITE_URL } from "@/lib/site";

export function generateStaticParams() {
  return [{ slug: [] as string[] }, ...DOCS.map((d) => ({ slug: [d.slug] }))];
}

export async function generateMetadata({ params }: { params: Promise<{ slug?: string[] }> }): Promise<Metadata> {
  const { slug } = await params;
  const which = slug?.[0] ?? DOCS[0].slug;
  const meta = DOCS.find((d) => d.slug === which);
  if (!meta) return {};
  const path = slug?.[0] ? `/docs/${meta.slug}` : "/docs";
  return {
    title: meta.title,
    description: meta.blurb,
    alternates: { canonical: path },
  };
}

export default async function DocPage({ params }: { params: Promise<{ slug?: string[] }> }) {
  const { slug } = await params;
  const which = slug?.[0] ?? DOCS[0].slug;
  const doc = getDoc(which);
  if (!doc) notFound();

  // Home → Docs → <this doc>
  const crumbs = [
    { name: "Home", item: `${SITE_URL}/` },
    { name: "Docs", item: `${SITE_URL}/docs` },
  ];
  if (slug?.[0]) crumbs.push({ name: doc.meta.title, item: `${SITE_URL}/docs/${doc.meta.slug}` });
  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: c.item,
    })),
  };

  return (
    <>
      <JsonLd data={breadcrumb} />
      <DocsContent content={doc.content} />
    </>
  );
}
