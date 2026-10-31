"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { sectionLabel } from "./nav";
import { ServiceStatus } from "./ServiceStatus";

export function TopBar() {
  const pathname = usePathname();
  const previous = useRef(pathname);

  // After client-side route changes (not the first load, where the skip link comes first),
  // move focus to the main region so keyboard and screen-reader users start at the content.
  useEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [pathname]);

  return (
    <div className="flex flex-col gap-3 border-b border-line px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
      <p className="font-mono text-xs uppercase tracking-[0.16em] text-muted">
        Workspace <span aria-hidden>/</span> <span className="text-ink">{sectionLabel(pathname)}</span>
      </p>
      <ServiceStatus />
    </div>
  );
}
