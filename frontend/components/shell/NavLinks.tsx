"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, isActive } from "./nav";

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`relative flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2.5 text-[15px] transition-colors ${
                active
                  ? "bg-accent-tint font-medium text-accent-soft before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-accent"
                  : "text-muted hover:bg-panel hover:text-ink"
              }`}
            >
              <span aria-hidden className="w-5 text-center font-mono">{item.glyph}</span>
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
