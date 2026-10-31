export const NAV_ITEMS = [
  { href: "/", label: "Search", glyph: "⌕" },
  { href: "/library", label: "Library", glyph: "▤" },
  { href: "/graph", label: "Graph", glyph: "⌘" },
  { href: "/dashboard", label: "Dashboard", glyph: "▥" },
] as const;

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function sectionLabel(pathname: string): string {
  return NAV_ITEMS.find((item) => isActive(pathname, item.href))?.label ?? "CiteHop";
}
