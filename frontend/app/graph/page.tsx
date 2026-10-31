import type { Metadata } from "next";
import Link from "next/link";

import { GraphExplorer, type SearchMethod } from "@/components/graph/GraphExplorer";
import { EmptyState, ErrorState, MetaRow, PageHeader, Panel, buttonPrimary, buttonSecondary, inputClass } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { load, type Loaded } from "@/lib/api/load";
import { graphHref } from "@/lib/library";

export const metadata: Metadata = { title: "Graph" };

const STATUS_TEXT: Record<Schemas["GraphStatusOut"]["status"], string> = {
  ready: "Ready",
  stale: "Stale: the graph was imported from an older corpus version",
  rebuilding: "Rebuilding",
  unavailable: "Unavailable",
};

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

export default async function GraphPage({ searchParams }: PageProps<"/graph">) {
  const params = await searchParams;
  const seedId = Number(first(params.article));
  const hasSeed = Number.isInteger(seedId) && seedId >= 1 && seedId <= 4_294_967_295;
  const query = first(params.q)?.trim().slice(0, 1000) || null;
  const method: SearchMethod = first(params.method) === "vector" ? "vector" : "keyword";
  const title = first(params.title)?.trim().slice(0, 200) || undefined;

  const [status, picks] = await Promise.all([
    load(() => api.GET("/api/v1/graph/status")),
    hasSeed ? Promise.resolve(null) : load(() => api.GET("/api/v1/articles", { params: { query: { title, page_size: 12 } } })),
  ]);
  const graph = status.ok ? status.data : null;

  return (
    <>
      <PageHeader eyebrow="Graph" title="Knowledge graph">
        <p>Real Wikipedia article links and categories from the pinned snapshot, read from Neo4j. A link between articles is not a citation or evidence that they agree.</p>
      </PageHeader>

      {graph && graph.status !== "ready" && (
        <div className="mb-6">
          <ErrorState title={`Graph ${graph.status}`}>
            <p>
              {STATUS_TEXT[graph.status]}. Imported {graph.imported_version ?? "nothing"}; MariaDB is at {graph.source_version ?? "an unknown version"}.{" "}
              {graph.status === "unavailable" ? "Start Neo4j and run `make graph-import`." : "Run `make graph-import` to refresh it."} Expansion and paths are disabled until then; Search and Library still work.
            </p>
            {graph.detail && <p className="mt-1 text-sm">{graph.detail}</p>}
          </ErrorState>
        </div>
      )}
      {!status.ok && (
        <div className="mb-6">
          <ErrorState title="Graph status could not be loaded">
            <p>{status.status === null ? "The CiteHop API is unreachable. Start it with make api." : (status.error?.message ?? `HTTP ${status.status}`)}</p>
          </ErrorState>
        </div>
      )}

      {hasSeed ? (
        <GraphExplorer key={seedId} seedId={seedId} status={graph} initialQuery={query} initialMethod={method} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <SeedPicker title={title} picks={picks} />
          <StatusPanel graph={graph} />
        </div>
      )}

      {hasSeed && graph && (
        <details className="mt-6 max-w-2xl text-sm text-muted">
          <summary className="cursor-pointer rounded-sm text-ink">Graph projection details</summary>
          <StatusPanel graph={graph} />
        </details>
      )}
    </>
  );
}

function SeedPicker({ title, picks }: { title?: string; picks: Loaded<Schemas["ArticlePage"]> | null }) {
  return (
    <EmptyState icon="◇" title="Choose an article to start from">
      <p className="mb-4">The graph opens on one article&apos;s neighborhood: its links in both directions and its categories.</p>
      <form action="/graph" className="mb-4 flex flex-wrap gap-2">
        <label htmlFor="seed-title" className="sr-only">Article title</label>
        <input id="seed-title" name="title" defaultValue={title} placeholder="Filter by title, e.g. neural" className={`${inputClass} max-w-xs`} />
        <button type="submit" className={buttonSecondary}>Filter</button>
      </form>
      {picks?.ok ? (
        picks.data.items.length ? (
          <ul className="flex flex-wrap gap-2">
            {picks.data.items.map((a) => (
              <li key={a.article_id}><Link href={graphHref(a.article_id)} className={`${buttonPrimary} !font-medium`}>{a.title}</Link></li>
            ))}
          </ul>
        ) : (
          <p>No article title contains “{title}”.</p>
        )
      ) : (
        <p role="alert" className="text-danger">Articles could not be loaded from the API.</p>
      )}
    </EmptyState>
  );
}

function StatusPanel({ graph }: { graph: Schemas["GraphStatusOut"] | null }) {
  return (
    <Panel className="mt-3">
      <h2 className="mb-2 text-[17px] font-medium">Graph projection</h2>
      {graph ? (
        <dl>
          <MetaRow label="Status">{STATUS_TEXT[graph.status]}</MetaRow>
          <MetaRow label="Imported version"><span className="font-mono">{graph.imported_version ?? "None"}</span></MetaRow>
          <MetaRow label="Corpus version"><span className="font-mono">{graph.source_version ?? "Unknown"}</span></MetaRow>
          {graph.imported_at && <MetaRow label="Imported at"><span className="font-mono">{graph.imported_at.replace("T", " ").slice(0, 16)} UTC</span></MetaRow>}
          {graph.counts && (
            <>
              <MetaRow label="Articles"><span className="font-mono">{graph.counts.articles ?? "—"}</span></MetaRow>
              <MetaRow label="Categories"><span className="font-mono">{graph.counts.categories ?? "—"}</span></MetaRow>
              <MetaRow label="Article links"><span className="font-mono">{graph.counts.links ?? "—"}</span></MetaRow>
              <MetaRow label="Category memberships"><span className="font-mono">{graph.counts.memberships ?? "—"}</span></MetaRow>
            </>
          )}
          {graph.detail && <MetaRow label="Detail">{graph.detail}</MetaRow>}
        </dl>
      ) : (
        <p role="alert" className="text-sm text-danger">Graph status could not be loaded from the API.</p>
      )}
    </Panel>
  );
}
