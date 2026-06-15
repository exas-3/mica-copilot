import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";
import { DOCS } from "@/lib/docs";
import { GUIDES } from "@/lib/guides";

// Generates /sitemap.xml — static pages + every dynamic /docs and /guides page (crawlers can't
// discover catch-all routes on their own).
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const e = (
    path: string,
    priority: number,
    changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"],
  ): MetadataRoute.Sitemap[number] => ({ url: `${SITE_URL}${path}`, lastModified: now, changeFrequency, priority });

  return [
    e("/", 1.0, "weekly"),
    e("/classify", 0.9, "monthly"),
    e("/guides", 0.8, "weekly"),
    ...GUIDES.map((g) => e(`/guides/${g.slug}`, 0.8, "monthly")),
    e("/docs", 0.7, "monthly"),
    ...DOCS.map((d) => e(`/docs/${d.slug}`, 0.6, "monthly")),
    e("/privacy", 0.3, "yearly"),
    e("/terms", 0.3, "yearly"),
  ];
}
