import type { SVGProps } from "react";

export type IconName = "search" | "library" | "graph" | "dashboard" | "arrow" | "spark" | "check";
const paths: Record<IconName, React.ReactNode> = {
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  library: <><rect x="4" y="4" width="5" height="16" rx="1" /><path d="M13 4v16M17 5l4 14M4 8h5M4 16h5" /></>,
  graph: <><circle cx="6" cy="6" r="3" /><circle cx="18" cy="8" r="3" /><circle cx="11" cy="19" r="3" /><path d="m9 6 6 1M7 9l3 7m6-5-4 5" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="11" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><path d="M14 18h7m-7 3h7" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  spark: <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />,
  check: <path d="m5 12 4 4L19 6" />,
};
export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]}</svg>;
}

export function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><svg width="25" height="25" viewBox="0 0 24 24" fill="none"><path d="m14 3-9 10h6l-1 8 9-11h-6l1-7Z" fill="currentColor" /></svg></span>;
}
