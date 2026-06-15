"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { slug: string; title: string; blurb: string };

export function DocsSidebar({ docs }: { docs: Item[] }) {
  const path = usePathname();
  const first = docs[0]?.slug;
  return (
    <nav className="docs-nav">
      <div className="eyebrow">Documentation</div>
      <div className="spacer" />
      {docs.map((d) => {
        const href = `/docs/${d.slug}`;
        const active = path === href || (path === "/docs" && d.slug === first);
        return (
          <Link key={d.slug} href={href} className={`docs-nav-item${active ? " active" : ""}`}>
            <span className="docs-nav-title">{d.title}</span>
            <span className="docs-nav-blurb">{d.blurb}</span>
          </Link>
        );
      })}
    </nav>
  );
}
