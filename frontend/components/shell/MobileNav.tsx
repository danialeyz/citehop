"use client";

import { BrandMark } from "@/components/icons";
import Link from "next/link";
import { useState } from "react";

import { NavLinks } from "./NavLinks";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-line bg-rail md:hidden">
      <div className="flex h-14 items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 rounded-md" aria-label="CiteHop home">
          <BrandMark />
          <span className="text-lg font-semibold tracking-[-0.03em]">citehop.</span>
        </Link>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((value) => !value)}
          className="rounded-[var(--radius-control)] border border-line px-3 py-1.5 text-sm text-ink"
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>
      <nav id="mobile-nav" aria-label="Main" hidden={!open} className="px-3 pb-3">
        <NavLinks onNavigate={() => setOpen(false)} />
      </nav>
    </div>
  );
}
