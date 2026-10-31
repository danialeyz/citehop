import Link from "next/link";

import { Chip, buttonSecondary } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import { METHOD_LABEL, type Method } from "@/lib/search";

const SCORE_LABEL: Record<Method, string> = { keyword: "FULLTEXT relevance", vector: "Cosine similarity" };
const small = `${buttonSecondary} !px-3 !py-1.5 !text-[13px]`;

export function SourceCard({
  hit,
  label,
  graphHref,
  onInspect,
}: {
  hit: Schemas["SearchHit"];
  label?: string;
  graphHref: string;
  onInspect: () => void;
}) {
  const method = hit.method === "keyword" ? "keyword" : "vector";
  return (
    <li id={`source-${hit.chunk_id}`} className="rounded-[var(--radius-card)] border border-line bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="grid size-7 place-items-center rounded-full border border-line-strong font-mono text-ink" aria-label={`Rank ${hit.rank}`}>
          {hit.rank}
        </span>
        <Chip tone="neutral">{METHOD_LABEL[method]}</Chip>
        <span className="font-mono text-muted" title="Method-specific; not comparable across methods or a probability">
          {SCORE_LABEL[method]} {hit.score.toFixed(3)}
        </span>
        {label && <Chip tone="accent">Cited as {label}</Chip>}
      </div>
      <h3 className="mt-3 text-lg font-medium leading-snug tracking-[-0.01em] [overflow-wrap:anywhere]">
        <Link href={`/library/${hit.article_id}`} className="hover:text-accent-soft">{hit.title}</Link>
      </h3>
      <p className="mt-2 line-clamp-4 whitespace-pre-line text-[15px] text-muted [overflow-wrap:anywhere]">{hit.passage}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={onInspect} className={small}>Inspect passage</button>
        <Link href={graphHref} className={small}>Explore connections</Link>
        <a href={hit.source_url} target="_blank" rel="noopener noreferrer" className={small}>
          Wikipedia<span aria-hidden>↗</span><span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>
    </li>
  );
}
