"use client";

import Link from "next/link";
import { Icon } from "@/components/icons";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, isActive } from "./nav";

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col gap-2">
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
                  ? "bg-accent-tint font-medium text-accent-soft"
                  : "text-muted hover:bg-panel hover:text-ink"
              }`}
            >
              <Icon name={item.icon} />
              {item.label}
              {active && <span aria-hidden className="ml-auto size-1.5 rounded-full bg-accent" />}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
