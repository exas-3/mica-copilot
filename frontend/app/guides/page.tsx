import type { Metadata } from "next";
import Link from "next/link";
import { GUIDES } from "@/lib/guides";

export const metadata: Metadata = {
  title: "MiCA Guides — Plain-English explainers of the EU crypto rules",
  description:
    "Short, cited explainers of EU MiCA: asset-referenced tokens, e-money tokens vs stablecoins, CASP authorisation, and crypto-asset white-paper requirements — each grounded in the regulation.",
  alternates: { canonical: "/guides" },
};

export default function GuidesIndex() {
  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">GUIDES</div>
        <h1>MiCA Guides</h1>
        <p>
          Plain-English, article-cited explainers of the EU Markets in Crypto-Assets Regulation
          (Regulation (EU) 2023/1114). Each links to the primary source and to the interactive tools.
        </p>
      </div>
      <div className="guide-list">
        {GUIDES.map((g) => (
          <Link key={g.slug} href={`/guides/${g.slug}`} className="guide-card">
            <span className="guide-card-title">{g.title}</span>
            <span className="guide-card-desc">{g.description}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
