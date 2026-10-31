"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { MetaRow, buttonSecondary } from "@/components/ui";

export type Inspected = {
  chunkId: string;
  articleId: number;
  title: string;
  sourceUrl: string;
  passage: string;
  rank: number;
  /** Set when opened from an answer citation. */
  label?: string;
};

/** Modal showing one exact stored passage. Native <dialog> provides focus trapping and Escape. */
export function PassageInspector({ item, graphHref, onClose }: { item: Inspected | null; graphHref: (articleId: number) => string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (item && !dialog.open) dialog.showModal();
    if (!item && dialog.open) dialog.close();
  }, [item]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current.close()}
      aria-labelledby="inspector-title"
      className="m-auto max-h-[90vh] w-[min(760px,calc(100vw-2rem))] overflow-y-auto rounded-[var(--radius-card)] border border-line-strong bg-panel p-0 text-ink backdrop:bg-page/80"
    >
      {item && (
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent">
                {item.label ? `Citation ${item.label} · exact passage` : "Exact passage"}
              </p>
              <h2 id="inspector-title" className="mt-1 text-2xl font-medium tracking-[-0.02em] [overflow-wrap:anywhere]">{item.title}</h2>
            </div>
            <button type="button" onClick={() => ref.current?.close()} className={`${buttonSecondary} !px-3`} aria-label="Close passage">
              ✕
            </button>
          </div>
          <blockquote className="mt-5 whitespace-pre-line rounded-xl border border-line bg-strip p-4 text-[15px] leading-relaxed [overflow-wrap:anywhere]">
            {item.passage}
          </blockquote>
          <p className="mt-3 text-sm text-muted">
            Stored passage text read from MariaDB by the API. A citation shows which passage the answer pointed at; it does not prove the passage supports the claim.
          </p>
          <dl className="mt-4">
            <MetaRow label="Search rank">{item.rank}</MetaRow>
            <MetaRow label="Chunk ID"><span className="font-mono text-xs">{item.chunkId}</span></MetaRow>
            <MetaRow label="Article ID"><span className="font-mono">{item.articleId}</span></MetaRow>
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link href={`/library/${item.articleId}`} className={buttonSecondary}>Open in Library</Link>
            <Link href={graphHref(item.articleId)} className={buttonSecondary}>Explore connections</Link>
            <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer" className={buttonSecondary}>
              Wikipedia<span aria-hidden>↗</span><span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
        </div>
      )}
    </dialog>
  );
}
