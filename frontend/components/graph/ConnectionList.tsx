"use client";
// Keyboard- and screen-reader-friendly equivalent of the canvas: every visible node and
// the selected node's connections, with direction spelled out.
import { nodeLabel, viewDegree, type GEdge, type GNode } from "@/lib/graph/model";

import type { Selection } from "./GraphCanvas";

type Props = {
  nodes: GNode[];
  edges: GEdge[];
  seed: string;
  selection: Selection;
  sourceRanks: Map<number, number>;
  onSelect: (selection: Selection) => void;
};

export function ConnectionList({ nodes, edges, seed, selection, sourceRanks, onSelect }: Props) {
  const degree = viewDegree(edges);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ordered = [...nodes].sort((a, b) =>
    a.id === seed ? -1 : b.id === seed ? 1 : a.kind !== b.kind ? (a.kind === "article" ? -1 : 1) : nodeLabel(a).localeCompare(nodeLabel(b), "en"),
  );
  const selectedId = selection?.kind === "node" ? selection.id : null;
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const outgoing = edges.filter((e) => e.source === selectedId && e.type === "LINKS_TO");
  const incoming = edges.filter((e) => e.target === selectedId && e.type === "LINKS_TO");
  const categories = edges.filter((e) => e.source === selectedId && e.type === "IN_CATEGORY");
  const members = edges.filter((e) => e.target === selectedId && e.type === "IN_CATEGORY");

  const item = (id: string, prefix?: string) => {
    const n = byId.get(id);
    if (!n) return null;
    return (
      <li key={`${prefix}-${id}`}>
        <button type="button" onClick={() => onSelect({ kind: "node", id })} className="text-left text-sm text-accent hover:text-accent-soft [overflow-wrap:anywhere]">
          {prefix && <span className="mr-1 text-muted">{prefix}</span>}{nodeLabel(n)}
        </button>
      </li>
    );
  };
  const group = (title: string, ids: string[], prefix: string) =>
    ids.length > 0 && (
      <div>
        <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{title} ({ids.length})</h4>
        <ul className="flex flex-col gap-1">{ids.map((id) => item(id, prefix))}</ul>
      </div>
    );

  return (
    <div className="grid gap-4 rounded-[var(--radius-card)] border border-line bg-panel p-4 md:grid-cols-2">
      <section aria-labelledby="graph-list-nodes">
        <h3 id="graph-list-nodes" className="mb-2 text-sm font-medium">Nodes in this view ({nodes.length})</h3>
        <ul className="flex max-h-[560px] flex-col gap-0.5 overflow-y-auto pr-1">
          {ordered.map((n) => {
            const rank = n.kind === "article" ? sourceRanks.get(n.article_id) : undefined;
            return (
              <li key={n.id}>
                <button
                  type="button"
                  aria-current={n.id === selectedId ? "true" : undefined}
                  onClick={() => onSelect({ kind: "node", id: n.id })}
                  className={`flex w-full items-start justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-card ${n.id === selectedId ? "bg-accent-tint text-accent-soft" : "text-ink"}`}
                >
                  <span className="[overflow-wrap:anywhere]">
                    <span aria-hidden className={n.kind === "category" ? "mr-1.5 text-amber" : "mr-1.5 text-accent"}>{n.kind === "category" ? "◆" : "▤"}</span>
                    <span className="sr-only">{n.kind === "category" ? "Category: " : "Article: "}</span>
                    {nodeLabel(n)}
                    {n.id === seed && <span className="ml-1.5 text-xs text-accent">(seed)</span>}
                    {rank !== undefined && <span className="ml-1.5 text-xs text-source">(source #{rank})</span>}
                  </span>
                  <span className="shrink-0 font-mono text-xs text-muted">{degree.get(n.id) ?? 0}<span className="sr-only"> connections in this view</span></span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section aria-labelledby="graph-list-connections" aria-live="polite">
        <h3 id="graph-list-connections" className="mb-2 text-sm font-medium [overflow-wrap:anywhere]">
          {selected ? <>Connections of {nodeLabel(selected)}</> : "Connections"}
        </h3>
        {selected ? (
          <div className="flex flex-col gap-3">
            {group("Links to", outgoing.map((e) => e.target), "→")}
            {group("Linked from", incoming.map((e) => e.source), "←")}
            {group("In categories", categories.map((e) => e.target), "◆")}
            {group("Member articles in view", members.map((e) => e.source), "▤")}
            {outgoing.length + incoming.length + categories.length + members.length === 0 && <p className="text-sm text-muted">No connections in this view.</p>}
          </div>
        ) : (
          <p className="text-sm text-muted">Choose a node to list its links, in both directions, and its categories.</p>
        )}
      </section>
    </div>
  );
}
