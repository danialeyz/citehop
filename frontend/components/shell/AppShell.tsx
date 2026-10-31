import { BrandMark, Icon } from "@/components/icons";
import Link from "next/link";
import type { ReactNode } from "react";

import { MobileNav } from "./MobileNav";
import { NavLinks } from "./NavLinks";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[224px_minmax(0,1fr)]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-accent px-4 py-2 font-semibold text-page focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-rail px-4 py-6 md:flex">
        <Link href="/" className="mb-12 flex items-center gap-3 rounded-md px-2" aria-label="CiteHop home">
          <BrandMark /><span className="text-[25px] font-semibold tracking-[-0.07em]">citehop<span className="text-accent">.</span></span>
        </Link>
        <p className="mb-4 px-3 text-[10px] font-medium uppercase tracking-[0.2em] text-muted">Your workspace</p>
        <nav aria-label="Main">
          <NavLinks />
        </nav>
        <div className="mt-auto rounded-2xl border border-line bg-panel p-4">
          <Icon name="spark" className="mb-3 text-accent" />
          <p className="text-sm font-medium">Curiosity, connected.</p>
          <p className="mt-2 text-xs leading-relaxed text-muted">Every answer starts with a source. See where yours leads.</p>
          <Link href="/graph" className="mt-4 flex items-center justify-between text-xs font-medium text-accent">Explore the graph <Icon name="arrow" width="15" height="15" /></Link>
        </div>
        <div className="mt-5 flex items-center gap-2 px-2 text-[10px] tracking-wide text-muted"><span className="size-1.5 rounded-full bg-accent" /> WIKIPEDIA ML CORPUS</div>
      </aside>
      <MobileNav />
      <div className="flex min-w-0 flex-col">
        <TopBar />
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 outline-none sm:px-8 lg:px-12 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
