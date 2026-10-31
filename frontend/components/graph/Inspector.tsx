"use client";
// Evidence inspector: source metadata and a real stored passage from MariaDB for the
// selected article, membership for a category, or provenance for a single edge.
import Link from "next/link";
import { useEffect, useState } from "react";

import { Chip, MetaRow, Panel, buttonSmall } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { load, type Loaded } from "@/lib/api/load";
import { isMaintenanceCategory, nodeLabel, type GEdge, type GNode, type GraphView } from "@/lib/graph/model";

import type { Selection } from "./GraphCanvas";

type Props = {
  node: GNode | undefined;
  edge: GEdge | undefined;
  view: GraphView;
  status: Schemas["GraphStatusOut"] | null;
  hits: Schemas["SearchHit"][];
  blocked: boolean;
  atCap: boolean;
  expanded: boolean;
  pathFrom: number | null;
  pathTo: number | null;
  onExpand: (nodeId: string) => void;
  onExplore: (articleId: number, title: string) => void;
  onSelect: (selection: Selection) => void;
  onPathEnd: (end: "from" | "to", articleId: number) => void;
};

const NO_LINK_EVIDENCE = "A link or shared category is not evidence that two articles agree.";

export function Inspector(props: Props) {
  const { node, edge } = props;
  return (
    <Panel className="!p-5">
      <h2 className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-accent">Inspector</h2>
      {node?.kind === "article" ? (
        <ArticleInspector {...props} node={node} />
      ) : node?.kind === "category" ? (
        <CategoryInspector node={node} view={props.view} onSelect={props.onSelect} />
      ) : edge ? (
        <EdgeInspector edge={edge} view={props.view} status={props.status} onSelect={props.onSelect} />
      ) : (
        <p className="text-sm text-muted">Select a node or an edge on the canvas, or use the connection list, to see its source data here.</p>
      )}
    </Panel>
  );
}

const detailCache = new Map<number, Loaded<Schemas["ArticleDetail"]>>();

function useArticleDetail(articleId: number) {
  const [state, setState] = useState<{ id: number; result: Loaded<Schemas["ArticleDetail"]> } | null>(null);
  const cached = detailCache.get(articleId);
  useEffect(() => {
    if (detailCache.has(articleId)) return;
    let live = true;
    load(() => api.GET("/api/v1/articles/{article_id}", { params: { path: { article_id: articleId }, query: { passage_page_size: 1 } } })).then((result) => {
      if (result.ok) detailCache.set(articleId, result);
      if (live) setState({ id: articleId, result });
    });
    return () => {
      live = false;
    };
  }, [articleId]);
  return cached ?? (state?.id === articleId ? state.result : null);
}

function ArticleInspector({ node, view, hits, blocked, atCap, expanded, pathFrom, pathTo, onExpand, onExplore, onPathEnd }: Props & { node: Extract<GNode, { kind: "article" }> }) {
  const detail = useArticleDetail(node.article_id);
  const hit = hits.find((h) => h.article_id === node.article_id);
  const isSeed = node.id === view.seed;
  const expandReason = blocked ? "Traversal is unavailable right now" : atCap ? "The view is at the 100-node cap" : expanded ? "Already expanded" : null;
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="mb-1 flex flex-wrap gap-1.5">
          <Chip tone="accent">Article</Chip>
          {isSeed && <Chip tone="accent">Seed</Chip>}
          {hit && <span className="inline-flex items-center rounded-[var(--radius-chip)] border border-source/40 px-2 py-0.5 text-xs text-source">Source #{hit.rank}</span>}
        </div>
        <h3 className="text-lg font-medium leading-snug [overflow-wrap:anywhere]">{node.title}</h3>
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonSmall} disabled={expandReason !== null} onClick={() => onExpand(node.id)} title={expandReason ?? undefined}>
          {expanded ? "Expanded" : "Expand neighborhood"}
        </button>
        {!isSeed && <button type="button" className={buttonSmall} disabled={blocked} onClick={() => onExplore(node.article_id, node.title)}>Explore from here</button>}
        <Link href={`/library/${node.article_id}`} className={buttonSmall}>Open article</Link>
      </div>
      {expandReason && !expanded && <p className="-mt-2 text-xs text-muted">{expandReason}.</p>}

      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonSmall} aria-pressed={pathFrom === node.article_id} onClick={() => onPathEnd("from", node.article_id)}>
          {pathFrom === node.article_id ? "✓ Path start" : "Set as path start"}
        </button>
        <button type="button" className={buttonSmall} aria-pressed={pathTo === node.article_id} onClick={() => onPathEnd("to", node.article_id)}>
          {pathTo === node.article_id ? "✓ Path end" : "Set as path end"}
        </button>
      </div>

      <dl>
        <MetaRow label="Article ID"><span className="font-mono">{node.article_id}</span></MetaRow>
        <MetaRow label="Revision"><span className="font-mono">{node.revision_id ?? "Not recorded"}</span></MetaRow>
        <MetaRow label="Source">
          <a href={node.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-soft [overflow-wrap:anywhere]">
            Wikipedia ↗<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </MetaRow>
        {detail?.ok && (
          <MetaRow label="Article links in MariaDB"><span className="font-mono">{detail.data.links.outgoing} out · {detail.data.links.incoming} in</span></MetaRow>
        )}
      </dl>

      {hit && (
        <figure className="rounded-[var(--radius-control)] border border-source/30 bg-page p-3">
          <figcaption className="mb-1.5 font-mono text-[11px] text-source">Retrieved passage · rank {hit.rank} · {hit.method}</figcaption>
          <p className="line-clamp-[8] whitespace-pre-line text-sm text-ink/90 [overflow-wrap:anywhere]">{hit.passage}</p>
        </figure>
      )}

      {detail === null ? (
        <p role="status" className="text-sm text-muted">Loading stored passage…</p>
      ) : !detail.ok ? (
        <p role="alert" className="text-sm text-danger">
          {detail.status === 404 ? "This article is in the graph snapshot but not in MariaDB; the graph may be stale." : (detail.error?.message ?? "Article details could not be loaded from MariaDB.")}
        </p>
      ) : (
        <>
          {detail.data.revision_id !== node.revision_id && node.revision_id !== null && (
            <p role="alert" className="text-sm text-amber">The graph snapshot has revision {node.revision_id}, MariaDB has {detail.data.revision_id}. Reimport the graph.</p>
          )}
          {!hit && (detail.data.passages.items[0] ? (
            <figure className="rounded-[var(--radius-control)] border border-line bg-page p-3">
              <figcaption className="mb-1.5 font-mono text-[11px] text-muted">Stored passage #1 of {detail.data.passages.total} · {detail.data.corpus_version}</figcaption>
              <p className="line-clamp-[8] whitespace-pre-line text-sm text-ink/90 [overflow-wrap:anywhere]">{detail.data.passages.items[0].text}</p>
            </figure>
          ) : (
            <p className="text-sm text-muted">No stored passages for this article under the current chunk configuration.</p>
          ))}
          <div>
            <p className="mb-1.5 text-xs text-muted">{detail.data.categories.length} categories in MariaDB</p>
            <ul className="flex flex-wrap gap-1">
              {detail.data.categories.filter((c) => !isMaintenanceCategory(c)).slice(0, 8).map((c) => <li key={c} className="max-w-full"><Chip>{c}</Chip></li>)}
            </ul>
          </div>
        </>
      )}
      <p className="text-xs text-muted">{NO_LINK_EVIDENCE}</p>
    </div>
  );
}

function CategoryInspector({ node, view, onSelect }: { node: Extract<GNode, { kind: "category" }>; view: GraphView; onSelect: Props["onSelect"] }) {
  const members = view.edges.filter((e) => e.type === "IN_CATEGORY" && e.target === node.id).map((e) => view.nodes.find((n) => n.id === e.source)).filter((n) => n !== undefined);
  const maintenance = isMaintenanceCategory(node.name);
  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="mb-1 flex gap-1.5"><Chip>Category</Chip>{maintenance && <Chip tone="neutral">Likely maintenance</Chip>}</div>
        <h3 className="text-lg font-medium leading-snug [overflow-wrap:anywhere]">{node.name}</h3>
      </div>
      {maintenance && <p className="text-sm text-muted">The name matches a Wikipedia housekeeping pattern. It groups articles by page upkeep, not by topic.</p>}
      <Link href={`/library?category=${encodeURIComponent(node.name)}`} className={`${buttonSmall} self-start`}>List its articles in the Library</Link>
      <div>
        <p className="mb-1.5 text-xs text-muted">{members.length} member {members.length === 1 ? "article" : "articles"} in this view</p>
        <ul className="flex flex-col gap-1">
          {members.map((m) => (
            <li key={m.id}><button type="button" className="text-left text-sm text-accent hover:text-accent-soft [overflow-wrap:anywhere]" onClick={() => onSelect({ kind: "node", id: m.id })}>{nodeLabel(m)}</button></li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-muted">Category hubs are not expanded: one category can span most of the corpus.</p>
    </div>
  );
}

function EdgeInspector({ edge, view, status, onSelect }: { edge: GEdge; view: GraphView; status: Schemas["GraphStatusOut"] | null; onSelect: Props["onSelect"] }) {
  const source = view.nodes.find((n) => n.id === edge.source);
  const target = view.nodes.find((n) => n.id === edge.target);
  const end = (n: GNode | undefined, id: string) => (
    <button type="button" className="text-left text-accent hover:text-accent-soft [overflow-wrap:anywhere]" onClick={() => onSelect({ kind: "node", id })}>{n ? nodeLabel(n) : id}</button>
  );
  return (
    <div className="flex flex-col gap-3">
      <Chip tone={edge.type === "IN_CATEGORY" ? "category" : "accent"}>{edge.type === "IN_CATEGORY" ? "Category membership" : "Article link"}</Chip>
      <p className="text-sm leading-relaxed">
        {end(source, edge.source)} <span className="text-muted">{edge.type === "IN_CATEGORY" ? "is in the category" : "links to"}</span> {end(target, edge.target)}
      </p>
      <p className="text-sm text-muted">
        {edge.type === "IN_CATEGORY"
          ? "Category membership recorded in the pinned Wikipedia revision."
          : "The source article's pinned revision contains a hyperlink to the target. The direction is the link's direction."}
      </p>
      <dl>
        <MetaRow label="Relationship"><span className="font-mono">{edge.type}</span></MetaRow>
        <MetaRow label="Snapshot"><span className="font-mono">{view.graphVersion}</span></MetaRow>
        {status?.imported_at && <MetaRow label="Imported">{status.imported_at.replace("T", " ").slice(0, 16)} UTC</MetaRow>}
      </dl>
      <p className="text-xs text-muted">{NO_LINK_EVIDENCE}</p>
    </div>
  );
}
