"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { REPO_URL } from "@/lib/site";

const NAV = [
  { href: "/", label: "Ask MiCA" },
  { href: "/classify", label: "Classify" },
  { href: "/guides", label: "Guides" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">MiCA Copilot</span>
          <span className="brand-sub">EU crypto-regulation, grounded &amp; cited</span>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={path === n.href ? "active" : ""}>
              {n.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="main">{children}</main>
      <footer className="site-footer">
        <span className="site-footer-note">
          A final project for the AUEB <em>“AI for Developers: Design, Build, Deploy LLM-powered
          Applications”</em> course · educational tool,
          answers are AI-generated and <strong>not legal advice</strong>.
        </span>
        <nav className="site-footer-links">
          <Link href="/guides">Guides</Link>
          <Link href="/docs">Docs</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer">GitHub ↗</a>
        </nav>
      </footer>
    </div>
  );
}
