import { LegalDoc } from "@/components/LegalDoc";

export const metadata = {
  title: "Privacy Policy — MiCA Copilot",
  description: "How the MiCA Compliance Copilot handles your data.",
};

const CONTENT = `
MiCA Compliance Copilot ("the Service", at **mica.exadaktylos.xyz**) is a non-commercial,
educational tool. This policy explains what data is processed when you use it. We have designed
the Service to process as little personal data as possible.

## Who is responsible

The data controller is **Stergios Exadaktylos**, operating the Service as an independent
educational project. Contact for any privacy question or request: **exas03@gmail.com**.

## What we process, and why

**The questions you type, and the answers given.** When you ask a question, its text is sent to
**Anthropic** (see *Third parties* below) to generate an answer. We also **store the question and
the answer in our own database** (on our own server) to monitor quality, debug, and improve the
Service. These logs are kept **separate from the AI system — the assistant cannot read past
conversations** — are **not linked to your identity** (the Service has no accounts and we do not
record your name), are **not shared** with anyone, and are **not used to train AI models.**
*Please do not enter personal, confidential, or sensitive information into the Service.*

**Technical connection data.** Like any website, serving the Service involves processing your IP
address and basic request metadata (e.g. browser type, timestamp, page requested). This is handled
by **Cloudflare** (our network provider) and may appear briefly in short-lived operational logs. It
is used only to deliver, secure, and debug the Service.

**No accounts, no advertising, no cross-site tracking.** The Service has no sign-up or login and
shows no ads.

**Analytics.** We use **Plausible Analytics**, a privacy-friendly, **cookieless** tool that we
**self-host on our own server** — your data is not sent to a third-party analytics company. It
records only **aggregate** usage (page views, referrers, country, browser/device type) and does
**not** use cookies, build a profile of you, or track you across other websites. To count unique
visits it derives a hash from your IP address and user-agent using a salt that **rotates every 24
hours**, then discards it; it cannot be used to identify you. The analytics requests are proxied
through this site (the \`/pa/\` path) so your browser only ever contacts our own domain.

## Legal bases (GDPR)

- Transmitting your question to the AI to produce the answer you requested — **performance of the
  service you ask for / legitimate interests** (Art. 6(1)(b)/(f) GDPR).
- Logging questions and answers to monitor quality, debug, and improve the Service — **legitimate
  interests** (Art. 6(1)(f) GDPR).
- Keeping the Service available and secure (network data, abuse prevention) — **legitimate
  interests** (Art. 6(1)(f) GDPR).
- Aggregate, cookieless analytics to understand and improve the Service — **legitimate interests**
  (Art. 6(1)(f) GDPR).

## Cookies

The Service sets **no tracking or advertising cookies**, and our analytics (Plausible) is
**cookieless**. Cloudflare may set **strictly necessary** security cookies (e.g. \`__cf_bm\`) to
distinguish humans from bots and protect the Service; these are not used to profile you and, being
strictly necessary, do not require consent.

## Third parties (processors)

| Provider | Role | What it receives | Their policy |
|---|---|---|---|
| **Anthropic, PBC** | Generates answers (Claude API) | The text of your questions | [anthropic.com/legal/privacy](https://www.anthropic.com/legal/privacy) |
| **Cloudflare, Inc.** | Network / proxy in front of the app | Your IP and connection metadata | [cloudflare.com/privacypolicy](https://www.cloudflare.com/privacypolicy/) |

Under Anthropic's commercial API terms, inputs sent via the API are **not used to train its models**
and are retained only briefly for safety and abuse monitoring. Both providers are US-based; any
transfer of personal data outside the EEA relies on their Standard Contractual Clauses and data
processing terms.

## Retention

We retain the conversation logs (your questions and the answers) **only as long as necessary** for
the purposes above and delete them when no longer needed. They are stored on our own infrastructure
and are not linked to your identity. You can ask us to delete logged content at any time (see *Your
rights*). Any IP address in operational or edge logs is short-lived. Anthropic and Cloudflare retain
data according to their own policies linked above.

## Your rights

Under the GDPR you have the right to access, rectify, erase, restrict, or object to the processing
of your personal data, and to data portability. We store conversation logs **without any identifier
linking them to you**, so to act on an access or deletion request we may need details that let us
locate the relevant records (e.g. the approximate time and the content of your question). Contact us
at **exas03@gmail.com** with any request. You also have the right to lodge a complaint with a
supervisory authority — in Greece, the **Hellenic Data Protection Authority (HDPA)**,
[dpa.gr](https://www.dpa.gr/).

## Children

The Service is not directed to children under 16 and we do not knowingly process their data.

## Changes

We may update this policy; the "Last updated" date above reflects the latest version.

## Contact

Questions about this policy or your data: **exas03@gmail.com**.

---

*This Service provides general information about the EU Markets in Crypto-Assets Regulation and is
**not legal advice**. See the [Terms of Service](/terms).*
`;

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy" updated="15 June 2026">
      {CONTENT}
    </LegalDoc>
  );
}
