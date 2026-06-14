"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Ask MiCA" },
  { href: "/classify", label: "Classify" },
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
    </div>
  );
}
