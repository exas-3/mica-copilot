import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Generates /robots.txt. Allow all public crawlers (including AI crawlers — this is a public
// educational tool we want surfaced) and point them at the sitemap.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
