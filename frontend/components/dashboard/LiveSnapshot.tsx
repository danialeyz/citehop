// Live corpus and graph counts, read from the API on this request. Never mixed with saved runs.
import type { ReactNode } from "react";

import { LoadError } from "@/components/library/LoadError";
import { Chip, MetaRow, Panel } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import type { Loaded } from "@/lib/api/load";
import { formatCount, formatUtc, percent, shortHash } from "@/lib/dashboard";

function StatCard({ label, value, children }: { label: string; value: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-[var(--radius-card)] border border-line bg-card p-5">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="m-0 font-mono text-3xl font-medium tracking-[-0.03em] text-ink">{value}</dd>
      {children && <dd className="m-0 text-xs text-muted [overflow-wrap:anywhere]">{children}</dd>}
    </div>
  );
}

export function CorpusCards({ stats, retryHref }: { stats: Loaded<Schemas["Stats"]>; retryHref: string }) {
  if (!stats.ok) return <LoadError {...stats} subject="Live corpus counts" retryHref={retryHref} />;
  const c = stats.data.corpus;
  const configs = c.embedding_configs;
  // Coverage of the configuration that covers most chunks; any others are listed under it.
  const primary = [...configs].sort((a, b) => b.chunks - a.chunks)[0];

  return (
    <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Articles" value={formatCount(c.articles)}>
        {formatCount(c.smoke_articles)} in the smoke subset
      </StatCard>
      <StatCard label="Chunks" value={formatCount(c.chunks)}>
        Stored passages across every configuration
      </StatCard>
      <StatCard
        label="Embedding coverage"
        value={c.chunks === 0 ? "No chunks" : primary ? percent(primary.chunks, c.chunks) : "0%"}
      >
        {c.chunks === 0
          ? "Nothing has been chunked or embedded yet."
          : primary
            ? <>
                {formatCount(primary.chunks)} of {formatCount(c.chunks)} chunks embedded · {formatCount(primary.articles_covered)} of{" "}
                {formatCount(c.articles)} articles · config {shortHash(primary.embedding_config)}
                {configs.length > 1 && <> · {configs.length - 1} more {configs.length === 2 ? "configuration" : "configurations"} stored</>}
              </>
            : "No chunk has an embedding configuration."}
      </StatCard>
      <StatCard label="Loaded article links" value={formatCount(c.article_links)}>
        {formatCount(c.distinct_categories)} categories · {formatCount(c.category_memberships)} memberships
      </StatCard>
    </dl>
  );
}

const GRAPH_TONE: Record<string, { label: string; className: string }> = {
  ready: { label: "Ready", className: "border-accent/40 bg-accent-tint text-accent-soft" },
  stale: { label: "Stale", className: "border-amber/40 bg-amber-tint text-amber" },
  rebuilding: { label: "Rebuilding", className: "border-amber/40 bg-amber-tint text-amber" },
  unavailable: { label: "Unavailable", className: "border-danger/40 bg-danger-tint text-danger" },
};

export function GraphPanel({ graph, retryHref }: { graph: Loaded<Schemas["GraphStatusOut"]>; retryHref: string }) {
  if (!graph.ok) return <LoadError {...graph} subject="Graph status" retryHref={retryHref} />;
  const g = graph.data;
  const tone = GRAPH_TONE[g.status] ?? GRAPH_TONE.unavailable;
  return (
    <Panel>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[17px] font-medium">Neo4j graph projection</h3>
        <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-xs ${tone.className}`}>
          <span aria-hidden className="size-1.5 rounded-full bg-current" />
          {tone.label}
        </span>
      </div>
      {g.detail && <p className="mb-3 text-sm text-ink/85">{g.detail}</p>}
      {g.status === "stale" && (
        <p className="mb-3 text-sm text-amber">
          The graph shows {g.imported_version ?? "an unknown version"}, but MariaDB holds {g.source_version ?? "an unknown version"}.
          Counts below describe the imported snapshot, not the live corpus.
        </p>
      )}
      <div className="grid gap-x-8 sm:grid-cols-2">
        <dl>
          <MetaRow label="Article nodes"><span className="font-mono">{formatCount(g.counts?.articles)}</span></MetaRow>
          <MetaRow label="Category nodes"><span className="font-mono">{formatCount(g.counts?.categories)}</span></MetaRow>
          <MetaRow label="LINKS_TO edges"><span className="font-mono">{formatCount(g.counts?.links)}</span></MetaRow>
          <MetaRow label="IN_CATEGORY edges"><span className="font-mono">{formatCount(g.counts?.memberships)}</span></MetaRow>
        </dl>
        <dl>
          <MetaRow label="Imported corpus version"><span className="font-mono">{g.imported_version ?? "Never imported"}</span></MetaRow>
          <MetaRow label="MariaDB corpus version"><span className="font-mono">{g.source_version ?? "Unavailable"}</span></MetaRow>
          <MetaRow label="Last import">
            {g.imported_at ? <time dateTime={g.imported_at}>{formatUtc(g.imported_at)}</time> : "Not recorded"}
          </MetaRow>
          <MetaRow label="Traversal">
            {g.status === "ready" ? <Chip tone="accent">Enabled</Chip> : <Chip tone="neutral">Disabled until ready</Chip>}
          </MetaRow>
        </dl>
      </div>
    </Panel>
  );
}
