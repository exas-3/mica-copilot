// Evergreen, cited MiCA explainer guides — the indexable, organic-search content layer.
// Each is grounded in the Regulation (EU) 2023/1114 ("MiCA", EUR-Lex CELEX 32023R1114) with
// article-level references, and links back to the interactive tools. General information, not
// legal advice — every page repeats that and links to the primary source.

export type Guide = {
  slug: string;
  title: string;        // <h1> + SEO title
  description: string;  // meta description (~150–160 chars)
  keywords: string[];
  updated: string;
  body: string;         // markdown
};

const EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114";
const NOT_ADVICE =
  "\n\n---\n\n*This is general information about MiCA, not legal advice. Always verify against the " +
  `[official text of Regulation (EU) 2023/1114](${EURLEX}) and consult a qualified professional.*`;
const CTA =
  "\n\n**Try it:** [Ask the MiCA Copilot](/) a follow-up question, or " +
  "[classify your token or service](/classify) to see which regime applies.";

export const GUIDES: Guide[] = [
  {
    slug: "what-is-an-asset-referenced-token",
    title: "What is an asset-referenced token (ART) under MiCA?",
    description:
      "An asset-referenced token (ART) under EU MiCA references a basket of assets or multiple currencies. Definition, authorisation, reserve and redemption rules — with article citations.",
    keywords: ["asset-referenced token", "ART", "MiCA", "crypto-asset", "stablecoin regulation"],
    updated: "15 June 2026",
    body:
      `An **asset-referenced token (ART)** is one of the three crypto-asset categories MiCA regulates. ` +
      `Under **Article 3(1)(6)**, an ART is a crypto-asset that "purports to maintain a stable value by ` +
      `referencing another value or right or a combination thereof, including one or more official ` +
      `currencies" — and that is **not** an e-money token.\n\n` +
      `## ART vs e-money token vs other crypto-asset\n` +
      `- References **one official currency** at par → likely an **e-money token (EMT)** (Title IV), not an ART.\n` +
      `- References a **basket** (several currencies, commodities like gold, or other crypto-assets) → **ART** (Title III).\n` +
      `- References nothing to stabilise value → an **"other" crypto-asset** under the Title II white-paper regime.\n\n` +
      `## Issuing an ART: the Title III regime\n` +
      `- **Authorisation (Article 16).** You generally must be authorised by your competent authority (or be a ` +
      `credit institution) **before** offering an ART to the public or seeking admission to trading.\n` +
      `- **Own funds (Article 35).** Issuers must hold minimum own funds (the higher of a fixed floor, a share of ` +
      `fixed overheads, or a percentage of the reserve).\n` +
      `- **Reserve of assets (Article 36).** The ART must be fully backed by a segregated reserve, maintained at ` +
      `all times and managed to cover the risks of the referenced assets.\n` +
      `- **Custody of reserve assets (Article 37).**\n` +
      `- **Redemption right (Article 39).** Holders have a permanent right of redemption against the issuer.\n\n` +
      `**Significant** ARTs (large user base or market cap) are supervised by the **European Banking Authority (EBA)**.` +
      CTA + NOT_ADVICE,
  },
  {
    slug: "e-money-tokens-vs-stablecoins",
    title: "E-money tokens vs stablecoins under MiCA",
    description:
      "MiCA has no 'stablecoin' category — it splits them into e-money tokens (one official currency) and asset-referenced tokens (a basket). Who can issue an EMT and the redemption-at-par rule.",
    keywords: ["e-money token", "EMT", "stablecoin", "MiCA", "redemption at par"],
    updated: "15 June 2026",
    body:
      `"Stablecoin" is not a MiCA term. MiCA splits stablecoins into two regulated categories by **what they ` +
      `reference**:\n\n` +
      `- **E-money token (EMT)** — references **one official currency** (e.g. a euro- or dollar-pegged token). ` +
      `Defined in **Article 3(1)(7)**, governed by **Title IV**.\n` +
      `- **Asset-referenced token (ART)** — references a basket or anything other than a single currency. ` +
      `Governed by **Title III** (see our [ART guide](/guides/what-is-an-asset-referenced-token)).\n\n` +
      `## Who may issue an e-money token\n` +
      `Under **Article 48**, an EMT may be issued **only** by an authorised **credit institution** or an ` +
      `**electronic money institution (EMI)**. The issuer must publish a crypto-asset white paper and **notify ` +
      `its competent authority at least 40 working days** before offering the EMT to the public or seeking ` +
      `admission to trading.\n\n` +
      `## The defining protections\n` +
      `- **Redeemable at par, on demand (Article 49).** Holders can redeem an EMT at any time, at par value, ` +
      `**free of charge**.\n` +
      `- **No interest (Article 50).** Issuers and service providers may not grant interest on EMTs.\n\n` +
      `These par-value and redemption guarantees are why an EMT is treated as **electronic money** and held to a ` +
      `stricter issuer set than a general ART.` +
      CTA + NOT_ADVICE,
  },
  {
    slug: "casp-authorisation",
    title: "CASP authorisation under MiCA: do you need it?",
    description:
      "Providing crypto-asset services in the EU generally requires authorisation as a CASP under MiCA Article 59. The service list (a–j), the application, safeguarding, and the 1 July 2026 transitional deadline.",
    keywords: ["CASP", "crypto-asset service provider", "MiCA authorisation", "Article 59", "transitional period"],
    updated: "15 June 2026",
    body:
      `A **crypto-asset service provider (CASP)** is anyone providing one or more of the crypto-asset services ` +
      `listed in **Article 3(1)(16)**. To provide them in the EU you generally need **authorisation under ` +
      `Article 59** — operating without it is unlawful.\n\n` +
      `## The ten crypto-asset services (a–j)\n` +
      `(a) custody & administration on behalf of clients · (b) operation of a trading platform · (c) exchange of ` +
      `crypto-assets for funds · (d) exchange of crypto-assets for other crypto-assets · (e) execution of orders · ` +
      `(f) placing · (g) reception & transmission of orders · (h) advice · (i) portfolio management · ` +
      `(j) transfer services.\n\n` +
      `## Getting (and keeping) authorisation\n` +
      `- **Who can skip a fresh licence (Article 60).** Certain already-authorised financial entities (e.g. credit ` +
      `institutions, investment firms) may provide crypto-asset services by **notifying** their authority instead.\n` +
      `- **Application & assessment (Articles 62–63).** You apply to your competent authority, which assesses and ` +
      `grants or refuses the authorisation.\n` +
      `- **Safeguarding (Article 70).** CASPs must hold clients' crypto-assets and funds securely and separately ` +
      `from their own.\n` +
      `- Plus governance, conflicts-of-interest and complaints-handling duties (Articles 71–72).\n\n` +
      `## The transitional ("grandfathering") deadline\n` +
      `Under **Article 143**, Member States may allow firms that provided crypto-asset services under national law ` +
      `before **30 December 2024** to continue during a transitional period of up to 18 months — i.e. until ` +
      `**1 July 2026** — or until they are granted or refused CASP authorisation.` +
      CTA + NOT_ADVICE,
  },
  {
    slug: "crypto-asset-white-paper-requirements",
    title: "Crypto-asset white paper requirements under MiCA (Title II)",
    description:
      "Offering a crypto-asset that isn't an ART or EMT to the EU public means drawing up, notifying and publishing a MiCA white paper. Mandatory contents, marketing rules, retail withdrawal right, and the exemptions.",
    keywords: ["MiCA white paper", "crypto-asset white paper", "Title II", "offer to the public", "Article 6"],
    updated: "15 June 2026",
    body:
      `If you offer a crypto-asset that is **neither an ART nor an EMT** to the public in the EU, or seek its ` +
      `admission to trading, **Title II (Articles 4–15)** applies — most importantly, a **crypto-asset white ` +
      `paper**.\n\n` +
      `## The core obligations\n` +
      `- **Draw up a white paper (Article 6).** It must contain the mandatory information about the issuer, the ` +
      `project, the rights and obligations, the underlying technology and the risks — presented **fair, clear and ` +
      `not misleading**.\n` +
      `- **Marketing communications (Article 7).** Must be identifiable as such, consistent with the white paper, ` +
      `and not misleading.\n` +
      `- **Notify the competent authority (Article 8)** before publication; publish the white paper (Article 9).\n` +
      `- **Right of withdrawal (Article 13).** Retail holders generally get a 14-day withdrawal right when ` +
      `acquiring directly from an issuer or a CASP placing the asset.\n` +
      `- **Liability (Article 15).** The issuer is liable for a white paper that is misleading or omits key ` +
      `information.\n\n` +
      `## When you may be exempt (Article 4)\n` +
      `Some offers don't require a white paper — for example offers to **fewer than 150 persons per Member State**, ` +
      `**small offers** below €1,000,000 over 12 months, or offers solely to **qualified investors**. Conditions ` +
      `apply, so check the exact wording of **Article 4(2)**.` +
      CTA + NOT_ADVICE,
  },
];

export function getGuide(slug: string): Guide | undefined {
  return GUIDES.find((g) => g.slug === slug);
}
