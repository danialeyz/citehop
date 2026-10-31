import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { MobileNav } from "./MobileNav";
import { NavLinks } from "./NavLinks";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-accent px-4 py-2 font-semibold text-page focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-rail px-4 py-6 md:flex">
        <Link href="/" className="mb-8 block rounded-md px-1" aria-label="CiteHop home">
          <Image src="/logo-dark.svg" alt="" width={196} height={49} priority className="h-auto w-full" />
        </Link>
        <nav aria-label="Main">
          <NavLinks />
        </nav>
        <p className="mt-auto px-2 font-mono text-[11px] leading-relaxed text-muted">
          Wikipedia ML corpus
          <br />
          MariaDB vectors · Neo4j graph
        </p>
      </aside>
      <MobileNav />
      <div className="flex min-w-0 flex-col">
        <TopBar />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 outline-none sm:px-8 lg:px-10 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
