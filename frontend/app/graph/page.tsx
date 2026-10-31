import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState, MetaRow, PageHeader, Panel, buttonSecondary } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { load } from "@/lib/api/load";
import { METHOD_LABEL, parseGraphSearchContext, searchHref } from "@/lib/search";

export const metadata: Metadata = { title: "Graph" };

const STATUS_TEXT: Record<Schemas["GraphStatusOut"]["status"], string> = {
  ready: "Ready",
  stale: "Stale: the graph was imported from an older corpus version",
  rebuilding: "Rebuilding",
  unavailable: "Unavailable",
};

export default async function GraphPage({ searchParams }: PageProps<"/graph">) {
  const params = await searchParams;
  const raw = params.article;
  const context = parseGraphSearchContext(params);
  const seedId = Number(Array.isArray(raw) ? raw[0] : raw);
  const hasSeed = Number.isInteger(seedId) && seedId >= 1 && seedId <= 4_294_967_295;

  const [status, seed] = await Promise.all([
    load(() => api.GET("/api/v1/graph/status")),
    hasSeed
      ? load(() => api.GET("/api/v1/articles/{article_id}", { params: { path: { article_id: seedId }, query: { passage_page_size: 1 } } }))
      : Promise.resolve(null),
  ]);

  return (
    <>
      <PageHeader eyebrow="Graph" title="Knowledge graph">
        <p>Real Wikipedia article links and categories from the pinned snapshot. A link between articles is not a citation or evidence that they agree.</p>
      </PageHeader>

      {context && (
        <nav aria-label="Search context" className="mb-6 flex flex-col gap-3 rounded-[var(--radius-card)] border border-line bg-panel p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted [overflow-wrap:anywhere]">
            From {METHOD_LABEL[context.search.method]} search{" "}
            <strong className="font-medium text-ink">“{context.search.q}”</strong>
            {context.sources.length > 0 && <> · {context.sources.length} retrieved {context.sources.length === 1 ? "article" : "articles"}</>}
          </p>
          <Link href={searchHref(context.search)} className={buttonSecondary}>← Back to search results</Link>
        </nav>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <EmptyState
          icon="⌘"
          title="The interactive graph is not built yet"
          action={
            seed?.ok ? (
              <Link href={`/library/${seed.data.article_id}`} className={buttonSecondary}>Open “{seed.data.title}” in the Library</Link>
            ) : (
              <Link href="/library" className={buttonSecondary}>Choose an article in the Library</Link>
            )
          }
        >
          {seed?.ok ? (
            <p>
              You arrived from <strong className="font-medium text-ink [overflow-wrap:anywhere]">{seed.data.title}</strong>. It has{" "}
              {seed.data.links.outgoing} outgoing and {seed.data.links.incoming} incoming article links in MariaDB. Its explorable
              neighborhood will appear here once the graph view is built.
            </p>
          ) : hasSeed ? (
            <p>The requested seed article could not be loaded from the Library.</p>
          ) : (
            <p>Open an article in the Library and choose Explore connections to start from it.</p>
          )}
        </EmptyState>

        <Panel>
          <h2 className="mb-2 text-[17px] font-medium">Graph projection</h2>
          {status.ok ? (
            <dl>
              <MetaRow label="Status">{STATUS_TEXT[status.data.status]}</MetaRow>
              <MetaRow label="Imported version"><span className="font-mono">{status.data.imported_version ?? "None"}</span></MetaRow>
              <MetaRow label="Corpus version"><span className="font-mono">{status.data.source_version ?? "Unknown"}</span></MetaRow>
              {status.data.counts && (
                <>
                  <MetaRow label="Articles"><span className="font-mono">{status.data.counts.articles ?? "—"}</span></MetaRow>
                  <MetaRow label="Categories"><span className="font-mono">{status.data.counts.categories ?? "—"}</span></MetaRow>
                  <MetaRow label="Article links"><span className="font-mono">{status.data.counts.links ?? "—"}</span></MetaRow>
                </>
              )}
              {status.data.detail && <MetaRow label="Detail">{status.data.detail}</MetaRow>}
            </dl>
          ) : (
            <p role="alert" className="text-sm text-danger">Graph status could not be loaded from the API.</p>
          )}
        </Panel>
      </div>
    </>
  );
}
