import Link from "next/link";

import { Chip } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import { articleHref, graphHref, type ListState } from "@/lib/library";

const VISIBLE_CATEGORIES = 3;

export function ArticleCard({ article, state }: { article: Schemas["ArticleSummary"]; state: ListState }) {
  const shown = article.categories.slice(0, VISIBLE_CATEGORIES);
  const hidden = article.categories.length - shown.length;
  return (
    <li className="group flex flex-col gap-3 rounded-[var(--radius-card)] border border-line bg-card p-5 transition-colors hover:border-line-strong">
      <h2 className="text-lg font-medium leading-snug tracking-[-0.01em] [overflow-wrap:anywhere]">
        <Link href={articleHref(article.article_id, state)} className="rounded-sm hover:text-accent-soft">
          {article.title}
        </Link>
      </h2>
      <p className="font-mono text-xs text-muted">
        {article.chunk_count} {article.chunk_count === 1 ? "passage" : "passages"} · {article.length_chars.toLocaleString("en-US")} characters
      </p>
      {article.categories.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Categories">
          {shown.map((name) => (
            <li key={name} className="max-w-full"><Chip>{name}</Chip></li>
          ))}
          {hidden > 0 && <li><Chip tone="neutral">+{hidden} more</Chip></li>}
        </ul>
      )}
      <div className="mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-1 text-sm">
        <Link href={articleHref(article.article_id, state)} className="rounded-sm text-accent hover:text-accent-soft" aria-label={`Open ${article.title}`}>
          Open article ↗
        </Link>
        <Link href={graphHref(article.article_id)} className="rounded-sm text-muted hover:text-ink" aria-label={`Explore connections of ${article.title}`}>
          Explore connections
        </Link>
      </div>
    </li>
  );
}
