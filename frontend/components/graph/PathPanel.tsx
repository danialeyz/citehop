"use client";
// Two-article path mode over the bounded /graph/path endpoint (≤ 3 LINKS_TO hops).
import { Panel, buttonSmall } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import type { GraphProblem } from "@/lib/graph/errors";
import { LIMITS, type GraphView } from "@/lib/graph/model";

import type { Selection } from "./GraphCanvas";

export type PathState = {
  from: number | null;
  to: number | null;
  directed: boolean;
  status: "idle" | "loading" | "done" | "error";
  result: Schemas["GraphPath"] | null;
  problem: GraphProblem | null;
};

type Props = {
  path: PathState;
  view: GraphView;
  blocked: boolean;
  onChange: (next: Partial<Pick<PathState, "from" | "to" | "directed">>) => void;
  onRun: () => void;
  onClear: () => void;
  onSelect: (selection: Selection) => void;
};

export function PathPanel({ path, view, blocked, onChange, onRun, onClear, onSelect }: Props) {
  const articles = view.nodes.flatMap((n) => (n.kind === "article" ? [n] : [])).sort((a, b) => a.title.localeCompare(b.title, "en"));
  const ready = path.from !== null && path.to !== null && path.from !== path.to;
  const picker = (end: "from" | "to", label: string) => (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <select
        aria-label={`Path ${label.toLowerCase()} article`}
        className="w-full rounded-[var(--radius-control)] border border-line bg-page px-2 py-1.5 text-sm text-ink"
        value={path[end] ?? ""}
        onChange={(e) => onChange({ [end]: e.target.value ? Number(e.target.value) : null })}
      >
        <option value="">Choose an article in view…</option>
        {articles.map((a) => <option key={a.id} value={a.article_id}>{a.title}</option>)}
        {/* Keep an end chosen earlier even if Back removed it from the view. */}
        {path[end] !== null && !articles.some((a) => a.article_id === path[end]) && <option value={path[end]!}>Article {path[end]}</option>}
      </select>
    </label>
  );
  return (
    <Panel className="!p-5">
      <h2 className="mb-1 font-mono text-[11px] uppercase tracking-[0.18em] text-accent">Path between two articles</h2>
      <p className="mb-3 text-xs text-muted">
        Shortest chain of article links, at most {LIMITS.maxPathLinks} links. Categories are never used as shortcuts.
      </p>
      <div className="flex flex-col gap-2">
        {picker("from", "Start")}
        {picker("to", "End")}
        <label className="flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" className="accent-[var(--color-accent)]" checked={!path.directed} onChange={(e) => onChange({ directed: !e.target.checked })} />
          Ignore link direction
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={buttonSmall} disabled={!ready || blocked} onClick={onRun}>
            {path.status === "loading" ? "Finding path…" : "Find path"}
          </button>
          {(path.from !== null || path.to !== null || path.result) && <button type="button" className={buttonSmall} onClick={onClear}>Clear path</button>}
        </div>
      </div>
      <div aria-live="polite" className="mt-3">
        {path.status === "error" && path.problem && <p role="alert" className="text-sm text-danger">{path.problem.title}: {path.problem.message}</p>}
        {path.status === "done" && path.result && <PathResult result={path.result} view={view} onSelect={onSelect} />}
      </div>
    </Panel>
  );
}

function PathResult({ result, view, onSelect }: { result: Schemas["GraphPath"]; view: GraphView; onSelect: Props["onSelect"] }) {
  const scope = result.directed
    ? `Directed: follows links from the start article toward the end article, up to ${result.max_links} links.`
    : `Undirected: a link counts in either direction, up to ${result.max_links} links. Arrows keep each link's real direction.`;
  if (!result.found) {
    return (
      <div className="rounded-[var(--radius-control)] border border-line bg-page p-3 text-sm">
        <p className="font-medium">{result.message ?? `No path within ${result.max_links} links`}</p>
        <p className="mt-1 text-muted">{scope} This does not mean the articles are unrelated.</p>
      </div>
    );
  }
  const nodes = result.nodes;
  const missing = nodes.filter((n) => !view.nodes.some((v) => v.id === n.id)).length;
  return (
    <div className="rounded-[var(--radius-control)] border border-accent/40 bg-page p-3 text-sm">
      <p className="mb-2 font-medium">
        {result.edges.length === 0 ? "Start and end are the same article" : `${result.edges.length} ${result.edges.length === 1 ? "link" : "links"}`}
      </p>
      <ol className="flex flex-col gap-1">
        {nodes.map((n, i) => {
          const edge = result.edges[i];
          const forward = edge ? edge.source === n.id : true;
          return (
            <li key={n.id}>
              <button type="button" className="text-left text-accent hover:text-accent-soft [overflow-wrap:anywhere]" onClick={() => onSelect({ kind: "node", id: n.id })}>
                <span className="mr-1 font-mono text-xs text-muted">{i + 1}.</span>{n.title}
              </button>
              {edge && (
                <p className="ml-5 font-mono text-[11px] text-muted">{forward ? "↓ links to" : "↑ is linked from (the next article links here)"}</p>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-xs text-muted">{scope} Snapshot {result.graph_version}.</p>
      {missing > 0 && <p className="mt-1 text-xs text-amber">{missing} path {missing === 1 ? "article" : "articles"} could not be added: the view is at its 100-node cap.</p>}
    </div>
  );
}
