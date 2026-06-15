import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GUIDES, getGuide } from "@/lib/guides";
import { LegalDoc } from "@/components/LegalDoc";
import { JsonLd } from "@/components/JsonLd";
import { SITE_URL, SITE_NAME, AUTHOR } from "@/lib/site";

export function generateStaticParams() {
  return GUIDES.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const g = getGuide(slug);
  if (!g) return {};
  return {
    title: g.title,
    description: g.description,
    keywords: g.keywords,
    alternates: { canonical: `/guides/${g.slug}` },
    openGraph: { type: "article", title: g.title, description: g.description, url: `${SITE_URL}/guides/${g.slug}` },
  };
}

export default async function GuidePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const g = getGuide(slug);
  if (!g) notFound();

  const article = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: g.title,
    description: g.description,
    inLanguage: "en",
    url: `${SITE_URL}/guides/${g.slug}`,
    author: { "@id": `${SITE_URL}/#person`, name: AUTHOR },
    publisher: { "@id": `${SITE_URL}/#org`, name: SITE_NAME },
    isAccessibleForFree: true,
    about: "Markets in Crypto-Assets Regulation (EU) 2023/1114",
  };
  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: `${SITE_URL}/` },
      { "@type": "ListItem", position: 2, name: "Guides", item: `${SITE_URL}/guides` },
      { "@type": "ListItem", position: 3, name: g.title, item: `${SITE_URL}/guides/${g.slug}` },
    ],
  };

  return (
    <>
      <JsonLd data={[article, breadcrumb]} />
      <LegalDoc title={g.title} updated={g.updated} eyebrow="GUIDE">
        {g.body}
      </LegalDoc>
    </>
  );
}
