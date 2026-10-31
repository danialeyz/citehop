export const NAV_ITEMS = [
  { href: "/", label: "Search", icon: "search" },
  { href: "/library", label: "Library", icon: "library" },
  { href: "/graph", label: "Graph", icon: "graph" },
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
] as const;

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function sectionLabel(pathname: string): string {
  return NAV_ITEMS.find((item) => isActive(pathname, item.href))?.label ?? "CiteHop";
}
