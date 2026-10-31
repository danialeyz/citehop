import Link from "next/link";

import { buttonSecondary } from "@/components/ui";

type Props = { page: number; pages: number; href: (page: number) => string; label: string };

/** Previous/next links plus a page indicator. Out-of-range pages are not linked. */
export function Pagination({ page, pages, href, label }: Props) {
  if (pages <= 1) return null;
  const disabled = `${buttonSecondary} pointer-events-none opacity-40`;
  return (
    <nav aria-label={label} className="mt-6 flex flex-wrap items-center justify-between gap-3">
      {page > 1 ? (
        <Link href={href(Math.min(page - 1, pages))} className={buttonSecondary} rel="prev">
          ← Previous
        </Link>
      ) : (
        <span aria-disabled="true" className={disabled}>← Previous</span>
      )}
      <p className="font-mono text-sm text-muted" aria-current="page">
        Page {page} of {pages}
      </p>
      {page < pages ? (
        <Link href={href(page + 1)} className={buttonSecondary} rel="next">
          Next →
        </Link>
      ) : (
        <span aria-disabled="true" className={disabled}>Next →</span>
      )}
    </nav>
  );
}
