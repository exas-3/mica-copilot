import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Instrument_Serif } from "next/font/google";
import "./globals.css";
import { Shell } from "@/components/Shell";
import { JsonLd } from "@/components/JsonLd";
import { SITE_URL, SITE_NAME, SITE_DESC, SITE_TAGLINE, AUTHOR, REPO_URL } from "@/lib/site";

const serif = Instrument_Serif({ weight: "400", subsets: ["latin"], variable: "--font-serif" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — Ask, classify & cite EU crypto-asset rules`,
    template: "%s · MiCA Copilot",
  },
  description: SITE_DESC,
  applicationName: SITE_NAME,
  keywords: [
    "MiCA",
    "Markets in Crypto-Assets Regulation",
    "Regulation (EU) 2023/1114",
    "EU crypto regulation",
    "asset-referenced token",
    "e-money token",
    "CASP authorisation",
    "crypto-asset white paper",
    "ESMA register",
  ],
  authors: [{ name: AUTHOR }],
  creator: AUTHOR,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESC,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: SITE_DESC,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
  category: "technology",
  // To enable Google Search Console, paste the verification token:
  // verification: { google: "PASTE_TOKEN_HERE" },
};

export const viewport: Viewport = {
  themeColor: "#1a3e72",
};

// Site-wide knowledge graph (Person → Organization → WebSite), linked by @id. Rendered in the
// server layout so it's in the initial HTML for crawlers.
const GRAPH = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Person",
      "@id": `${SITE_URL}/#person`,
      name: AUTHOR,
      url: SITE_URL,
    },
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#org`,
      name: SITE_NAME,
      url: SITE_URL,
      founder: { "@id": `${SITE_URL}/#person` },
      logo: `${SITE_URL}/icon-512.png`,
      sameAs: [REPO_URL],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: SITE_NAME,
      description: SITE_DESC,
      publisher: { "@id": `${SITE_URL}/#org` },
      inLanguage: "en",
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} ${serif.variable}`}>
      <body>
        <JsonLd data={GRAPH} />
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
