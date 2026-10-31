"use client";
// Search-to-graph highlighting: runs one retrieval (no generation) and marks the
// articles it returned. Scores stay on the search page; only ranks are shown here.
import { Panel, buttonSmall, inputClass } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import type { GraphView } from "@/lib/graph/model";
import { filterLabels, type Filters, type Method } from "@/lib/search";

import type { Selection } from "./GraphCanvas";

export type SearchState = {
  query: string;
  method: Method;
  filters: Filters; // carried from the Search page; applied in SQL like there
  status: "idle" | "loading" | "done" | "error";
  hits: Schemas["SearchHit"][];
  message: string | null;
  ran: { query: string; method: Method } | null;
  carried: number[]; // article IDs the Search page retrieved, shown until a search here completes
};

type Props = {
  search: SearchState;
  view: GraphView;
  onChange: (next: Partial<Pick<SearchState, "query" | "method" | "filters">>) => void;
  onRun: () => void;
  onClear: () => void;
  onSelect: (selection: Selection) => void;
  onExplore: (articleId: number, title: string) => void;
};

export function SearchHighlight({ search, view, onChange, onRun, onClear, onSelect, onExplore }: Props) {
  // One row per article, at its best rank.
  const articles = search.hits.filter((hit, i) => search.hits.findIndex((h) => h.article_id === hit.article_id) === i);
  const inView = new Set(view.nodes.map((n) => n.id));
  const filters = filterLabels(search.filters);
  return (
    <Panel className="!p-5">
      <h2 className="mb-1 font-mono text-[11px] uppercase tracking-[0.18em] text-accent">Highlight search sources</h2>
      <p className="mb-3 text-xs text-muted">Retrieves passages only; no answer is generated. Retrieved articles get a Source badge.</p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          onRun();
        }}
      >
        <label className="sr-only" htmlFor="graph-search">Query</label>
        <input id="graph-search" className={inputClass} value={search.query} maxLength={1000} placeholder="e.g. vanishing gradient" onChange={(e) => onChange({ query: e.target.value })} />
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Search method" className="rounded-[var(--radius-control)] border border-line bg-page px-2 py-1.5 text-sm text-ink" value={search.method} onChange={(e) => onChange({ method: e.target.value === "keyword" ? "keyword" : "vector" })}>
            <option value="keyword">Keyword</option>
            <option value="vector">Meaning</option>
          </select>
          <button type="submit" className={buttonSmall} disabled={!search.query.trim() || search.status === "loading"}>
            {search.status === "loading" ? "Searching…" : "Highlight"}
          </button>
          {(search.ran || search.carried.length > 0) && <button type="button" className={buttonSmall} onClick={onClear}>Clear</button>}
        </div>
        {filters.length > 0 && (
          <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
            Filters from your search: {filters.join(" · ")}
            <button type="button" className="text-accent hover:text-accent-soft" onClick={() => onChange({ filters: {} })}>Remove</button>
          </p>
        )}
      </form>
      <div aria-live="polite" className="mt-3">
        {search.status === "error" && <p role="alert" className="text-sm text-danger">Search failed: {search.message}</p>}
        {search.carried.length > 0 && search.status !== "done" && (
          <p className="text-xs text-muted">
            {search.carried.length} {search.carried.length === 1 ? "article" : "articles"} retrieved on the Search page are badged in their result order
            {search.status === "loading" ? "; loading their passages…" : "."}
          </p>
        )}
        {search.status === "done" && search.ran && (
          articles.length === 0 ? (
            <p className="text-sm text-muted">No passages matched “{search.ran.query}”.</p>
          ) : (
            <>
              <p className="mb-2 text-xs text-muted">
                {articles.length} {articles.length === 1 ? "article" : "articles"} for “{search.ran.query}” ({search.ran.method === "vector" ? "meaning" : "keyword"}),{" "}
                {articles.filter((h) => inView.has(`article:${h.article_id}`)).length} in this view
              </p>
              <ol className="flex flex-col gap-1.5">
                {articles.map((hit) => {
                  const id = `article:${hit.article_id}`;
                  return (
                    <li key={hit.article_id} className="flex items-start justify-between gap-2 text-sm">
                      <span className="flex min-w-0 gap-1.5">
                        <span className="font-mono text-xs text-source">#{hit.rank}</span>
                        {inView.has(id) ? (
                          <button type="button" className="text-left text-accent hover:text-accent-soft [overflow-wrap:anywhere]" onClick={() => onSelect({ kind: "node", id })}>{hit.title}</button>
                        ) : (
                          <span className="[overflow-wrap:anywhere]">{hit.title} <span className="text-xs text-muted">(not in view)</span></span>
                        )}
                      </span>
                      {!inView.has(id) && (
                        <button type="button" className="shrink-0 text-xs text-accent hover:text-accent-soft" onClick={() => onExplore(hit.article_id, hit.title)}>Explore</button>
                      )}
                    </li>
                  );
                })}
              </ol>
            </>
          )
        )}
      </div>
    </Panel>
  );
}
