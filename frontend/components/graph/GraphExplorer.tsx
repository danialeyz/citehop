"use client";
// Graph view state: bounded fetches, history (Back/Reset), selection, search highlight,
// and path mode. The canvas and the connection list render the same visible graph.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Chip, buttonSmall as smallButton } from "@/components/ui";
import { api, type Schemas } from "@/lib/api/client";
import { load, type Loaded as ApiLoaded } from "@/lib/api/load";
import { graphProblem, versionChanged, type GraphProblem } from "@/lib/graph/errors";
import {
  LIMITS, VersionMismatch, addPath, combineNeighborhoods, expandView, pushHistory, withoutMaintenance, nodeLabel, radialLayout, viewFromNeighborhood, visibleGraph,
  type GraphView, type Neighborhood, type RelType,
} from "@/lib/graph/model";

import { ConnectionList } from "./ConnectionList";
import { GraphCanvas, type Selection } from "./GraphCanvas";
import { Inspector } from "./Inspector";
import { PathPanel, type PathState } from "./PathPanel";
import { SearchHighlight, type SearchState } from "./SearchHighlight";

// Each entry carries the toolbar options it was fetched with, so Back/Reset restore both.
type Entry = { view: GraphView; label: string; options: Options };
type Loaded<T> = ApiLoaded<T> | { ok: false; status: number; error: null; mismatch: VersionMismatch };
const problemOf = (r: Exclude<Loaded<unknown>, { ok: true }>) =>
  "mismatch" in r ? versionChanged(r.mismatch.expected, r.mismatch.received) : graphProblem(r.status, r.error);
type Options = { hops: 1 | 2; categories: boolean; maintenance: boolean };
export type SearchMethod = "keyword" | "vector";

const HISTORY_LIMIT = 30;
const DEFAULT_OPTIONS: Options = { hops: 1, categories: true, maintenance: false };

type Props = {
  seedId: number;
  status: Schemas["GraphStatusOut"] | null;
  initialQuery: string | null;
  initialMethod: SearchMethod;
};

export function GraphExplorer({ seedId, status, initialQuery, initialMethod }: Props) {
  const [history, setHistory] = useState<Entry[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [trail, setTrail] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<GraphProblem | null>(null);
  const [mode, setMode] = useState<"canvas" | "list">("canvas");
  const [fitTick, setFitTick] = useState(0);
  const [search, setSearch] = useState<SearchState>({ query: initialQuery ?? "", method: initialMethod, status: "idle", hits: [], message: null, ran: null });
  const [path, setPath] = useState<PathState>({ from: null, to: null, directed: true, status: "idle", result: null, problem: null });
  const request = useRef(0);
  const pathRequest = useRef(0);

  const current = history.at(-1) ?? null;
  const view = current?.view ?? null;
  const options = current?.options ?? DEFAULT_OPTIONS;
  const blocked = (problem?.blocksTraversal ?? false) || path.status === "loading";

  const shown = useMemo(() => (view ? visibleGraph(view, { hideMaintenance: !options.maintenance }) : null), [view, options.maintenance]);

  const push = useCallback((entry: Entry, refit: boolean) => {
    setHistory((h) => pushHistory(h, entry, HISTORY_LIMIT));
    if (refit) setFitTick((t) => t + 1);
  }, []);

  // --- fetches ----------------------------------------------------------------------------

  /** Article links within `opts.hops`, plus the article's own categories when enabled. */
  const fetchNeighborhood = useCallback(async (articleId: number, opts: Options): Promise<Loaded<Neighborhood>> => {
    const get = (rel_types: RelType[], hops: number, max_nodes: number, max_edges: number) =>
      load(() => api.GET("/api/v1/graph/neighborhood", { params: { query: { article_id: articleId, hops, max_nodes, max_edges, rel_types } } }));
    const [links, categories] = await Promise.all([
      get(["LINKS_TO"], opts.hops, LIMITS.defaultNodes, LIMITS.defaultEdges),
      opts.categories ? get(["IN_CATEGORY"], 1, LIMITS.defaultNodes, LIMITS.defaultEdges) : Promise.resolve(null),
    ]);
    if (!links.ok) return links;
    if (categories && !categories.ok) return categories;
    // Leaving out housekeeping categories keeps them from spending the 100-node budget.
    const cats = categories && !opts.maintenance ? withoutMaintenance(categories.data) : (categories?.data ?? null);
    try {
      return { ok: true, data: combineNeighborhoods(links.data, cats) };
    } catch (error) {
      if (error instanceof VersionMismatch) return { ok: false, status: 409, error: null, mismatch: error };
      throw error;
    }
  }, []);

  /** Start a new exploration from `articleId` (initial load, Explore from here, depth/category change). */
  const explore = useCallback(async (articleId: number, opts: Options, label: string, replace = false) => {
    const token = ++request.current;
    setBusy(`Loading the neighborhood of ${label}…`);
    const result = await fetchNeighborhood(articleId, opts);
    if (token !== request.current) return; // a newer action superseded this one
    setBusy(null);
    if (!result.ok) {
      setProblem(problemOf(result));
      return;
    }
    setProblem(null);
    const entry = { view: viewFromNeighborhood(result.data), label, options: opts };
    if (replace) {
      setHistory([entry]);
      setFitTick((t) => t + 1);
    } else push(entry, true);
    setSelection(null);
    setTrail([]);
    const url = new URL(window.location.href);
    url.searchParams.set("article", String(articleId));
    window.history.replaceState(window.history.state, "", url);
  }, [fetchNeighborhood, push]);

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // Strict Mode mounts twice; load the seed once
    started.current = true;
    void explore(seedId, DEFAULT_OPTIONS, "the seed article", true);
  }, [explore, seedId]);

  const expand = useCallback(async (nodeId: string) => {
    if (!view) return;
    const node = view.nodes.find((n) => n.id === nodeId);
    if (!node || node.kind !== "article") return;
    const token = ++request.current;
    setBusy(`Expanding ${node.title}…`);
    const result = await fetchNeighborhood(node.article_id, options);
    if (token !== request.current) return;
    setBusy(null);
    if (!result.ok) {
      setProblem(problemOf(result));
      return;
    }
    try {
      const merged = expandView(view, nodeId, result.data);
      setProblem(null);
      push({ view: merged.view, label: `Expanded ${node.title} (+${merged.added.length})`, options }, false);
    } catch (error) {
      if (error instanceof VersionMismatch) setProblem(versionChanged(error.expected, error.received));
      else throw error;
    }
  }, [view, options, fetchNeighborhood, push]);

  const runPath = useCallback(async (from: number, to: number, directed: boolean) => {
    if (!view || busy) return;
    const token = ++pathRequest.current;
    setPath((p) => ({ ...p, from, to, directed, status: "loading", result: null, problem: null }));
    const result = await load(() => api.GET("/api/v1/graph/path", { params: { query: { source_id: from, target_id: to, directed } } }));
    if (token !== pathRequest.current) return;
    if (!result.ok) {
      const issue = graphProblem(result.status, result.error);
      setPath((p) => ({ ...p, status: "error", problem: issue }));
      if (issue.blocksTraversal) setProblem(issue);
      return;
    }
    setPath((p) => ({ ...p, status: "done", result: result.data }));
    if (!result.data.found) return;
    try {
      const merged = addPath(view, result.data);
      const names = result.data.nodes;
      // Save the merge when it adds nodes or only edges (path links cut earlier by the cap or
      // between nodes from different expansions), or when it marks the view truncated.
      if (merged.added.length || merged.dropped || merged.view.edges.length !== view.edges.length) {
        push({ view: merged.view, label: `Path ${names[0]?.title} → ${names.at(-1)?.title}`, options }, false);
      }
    } catch (error) {
      if (error instanceof VersionMismatch) setPath((p) => ({ ...p, status: "error", problem: versionChanged(error.expected, error.received) }));
      else throw error;
    }
  }, [view, options, busy, push]);

  const runSearch = useCallback(async (query: string, method: SearchMethod) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setSearch((s) => ({ ...s, query: trimmed, method, status: "loading", message: null }));
    const result = await load(() => api.POST("/api/v1/search", { body: { query: trimmed, method, k: 10 } }));
    setSearch((s) => {
      if (s.query !== trimmed || s.method !== method) return s; // the user changed it meanwhile
      if (!result.ok) return { ...s, status: "error", hits: [], ran: null, message: result.error?.message ?? (result.status === null ? "The API is unreachable." : `HTTP ${result.status}`) };
      return { ...s, status: "done", hits: result.data.hits, ran: { query: trimmed, method }, message: null };
    });
    const url = new URL(window.location.href);
    url.searchParams.set("q", trimmed);
    url.searchParams.set("method", method);
    window.history.replaceState(window.history.state, "", url);
  }, []);

  const searched = useRef(false);
  useEffect(() => {
    if (searched.current || !initialQuery) return;
    searched.current = true;
    void runSearch(initialQuery, initialMethod);
  }, [initialQuery, initialMethod, runSearch]);

  // --- navigation -------------------------------------------------------------------------

  const select = useCallback((next: Selection) => {
    setSelection(next);
    if (next?.kind === "node") setTrail((t) => [...t.filter((id) => id !== next.id), next.id].slice(-6));
  }, []);

  const back = () => {
    request.current++; // drop any in-flight result
    pathRequest.current++; // a late path result would merge into the view Back removed
    setBusy(null);
    setPath((p) => (p.status === "loading" ? { ...p, status: "idle" } : p));
    setHistory((h) => (h.length > 1 ? h.slice(0, -1) : h));
    setFitTick((t) => t + 1);
  };
  const reset = () => {
    request.current++;
    pathRequest.current++;
    setBusy(null);
    setHistory((h) => h.slice(0, 1)); // the pinned seed view and its options
    setSelection(null);
    setTrail([]);
    setPath({ from: null, to: null, directed: true, status: "idle", result: null, problem: null });
    setFitTick((t) => t + 1);
  };
  const resetLayout = () => {
    if (!view) return;
    push({ view: { ...view, positions: radialLayout(view) }, label: "Reset layout", options }, true);
  };
  // Options take effect only with the reload's history entry; a failed reload changes nothing.
  const changeOptions = (next: Options) => {
    const seed = view?.nodes.find((n) => n.id === view.seed);
    if (seed?.kind === "article") void explore(seed.article_id, next, seed.title);
  };

  // --- derived highlight state ------------------------------------------------------------

  const sourceRanks = useMemo(() => {
    const ranks = new Map<number, number>();
    for (const hit of search.hits) if (!ranks.has(hit.article_id)) ranks.set(hit.article_id, hit.rank);
    return ranks;
  }, [search.hits]);

  const pathNodes = useMemo(() => (path.result?.found ? path.result.nodes.map((n) => n.id) : []), [path.result]);
  const pathEdges = useMemo(() => new Set(path.result?.found ? path.result.edges.map((e) => `${e.source}|${e.type}|${e.target}`) : []), [path.result]);

  const selectedNode = selection?.kind === "node" ? view?.nodes.find((n) => n.id === selection.id) : undefined;
  const selectedEdge = selection?.kind === "edge" ? view?.edges.find((e) => e.id === selection.id) : undefined;
  const atCap = (view?.nodes.length ?? 0) >= LIMITS.maxNodes;

  // --- render -----------------------------------------------------------------------------

  if (!view || !shown) {
    return (
      <div className="flex flex-col gap-4">
        {problem ? <ProblemBanner problem={problem} onRetry={() => explore(seedId, options, "the seed article", true)} /> : (
          <div role="status" className="grid h-[420px] place-items-center rounded-[var(--radius-card)] border border-line bg-panel text-muted">
            {busy ?? "Loading the graph…"}
          </div>
        )}
      </div>
    );
  }

  const seedNode = view.nodes.find((n) => n.id === view.seed);
  const seedLinks = view.edges.filter((e) => e.type === "LINKS_TO" && (e.source === view.seed || e.target === view.seed)).length;

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar: every control is a visible button or input, usable without hover. */}
      <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-line bg-panel p-3">
        <button type="button" className={smallButton} onClick={back} disabled={history.length < 2} aria-label={history.length > 1 ? `Back: undo “${current?.label}”` : "Back"}>
          ← Back
        </button>
        <button type="button" className={smallButton} onClick={reset} disabled={history.length < 2 && !path.result}>Reset</button>
        <button type="button" className={smallButton} onClick={resetLayout}>Reset layout</button>
        <span className="mx-1 hidden h-5 w-px bg-line sm:block" aria-hidden />
        <label className="flex items-center gap-1.5 text-sm text-muted">
          Depth
          <select
            className="rounded-[var(--radius-control)] border border-line bg-page px-2 py-1 text-sm text-ink"
            value={options.hops}
            disabled={blocked || busy !== null}
            onChange={(e) => changeOptions({ ...options, hops: e.target.value === "2" ? 2 : 1 })}
          >
            <option value="1">1 hop</option>
            <option value="2">2 hops</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input type="checkbox" className="accent-[var(--color-amber)]" checked={options.categories} disabled={blocked || busy !== null}
            onChange={(e) => changeOptions({ ...options, categories: e.target.checked })} />
          Categories
        </label>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input type="checkbox" className="accent-[var(--color-amber)]" checked={!options.maintenance} disabled={!options.categories || blocked || busy !== null}
            onChange={(e) => changeOptions({ ...options, maintenance: !e.target.checked })} />
          Leave out maintenance categories
        </label>
        <div className="ml-auto flex rounded-[var(--radius-control)] border border-line p-0.5" role="group" aria-label="Display">
          {(["canvas", "list"] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}
              className={`rounded-[7px] px-3 py-1 text-sm ${mode === m ? "bg-accent-tint text-accent-soft" : "text-muted hover:text-ink"}`}>
              {m === "canvas" ? "Canvas" : "Connection list"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted" aria-live="polite">
        <span>
          Seed <strong className="font-medium text-ink [overflow-wrap:anywhere]">{seedNode ? nodeLabel(seedNode) : view.seed}</strong> · depth {view.hops} ·{" "}
          <span className="font-mono">{shown.nodes.length} nodes · {shown.edges.length} edges</span>
          {options.categories && !options.maintenance && <> · maintenance categories left out</>}
        </span>
        <span className="font-mono text-xs">snapshot {view.graphVersion}</span>
        {busy && <span role="status" className="text-accent-soft">{busy}</span>}
      </div>

      {view.truncated && (
        <p className="rounded-[var(--radius-control)] border border-amber/40 bg-amber-tint px-3 py-2 text-sm text-amber">
          <strong className="font-semibold">Showing a limited neighborhood.</strong> The API or the {LIMITS.maxNodes}-node / {LIMITS.maxEdges}-edge view cap left out some connections, so degree counts describe this view only.
          {atCap && " The view is full: go Back or Reset before expanding further."}
        </p>
      )}
      {seedLinks === 0 && view.nodes.length >= 1 && (
        <p className="rounded-[var(--radius-control)] border border-line bg-panel px-3 py-2 text-sm text-muted">
          This article has no article links to or from other loaded articles in the snapshot{view.relTypes.includes("IN_CATEGORY") ? "; only its categories are shown" : ""}.
        </p>
      )}
      {problem && <ProblemBanner problem={problem} onRetry={() => setProblem(null)} retryLabel="Dismiss" />}

      {trail.length > 1 && (
        <nav aria-label="Selection breadcrumbs" className="flex flex-wrap items-center gap-1 text-xs text-muted">
          {trail.map((id, i) => {
            const n = view.nodes.find((x) => x.id === id);
            if (!n) return null;
            return (
              <span key={id} className="flex items-center gap-1">
                {i > 0 && <span aria-hidden>›</span>}
                <button type="button" onClick={() => select({ kind: "node", id })} className="max-w-[16rem] truncate rounded px-1 hover:text-accent-soft" aria-current={selection?.kind === "node" && selection.id === id ? "true" : undefined}>
                  {nodeLabel(n)}
                </button>
              </span>
            );
          })}
        </nav>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          {mode === "canvas" ? (
            <div className="h-[62vh] min-h-[380px] overflow-hidden rounded-[var(--radius-card)] border border-line lg:h-[680px]">
              <GraphCanvas
                nodes={shown.nodes}
                edges={shown.edges}
                positions={view.positions}
                seed={view.seed}
                selection={selection}
                sourceRanks={sourceRanks}
                pathNodes={pathNodes}
                pathEdges={pathEdges}
                fitKey={`${fitTick}`}
                onSelect={select}
              />
            </div>
          ) : (
            <ConnectionList nodes={shown.nodes} edges={shown.edges} seed={view.seed} selection={selection} sourceRanks={sourceRanks} onSelect={select} />
          )}
          <Legend />
        </div>

        <aside className="flex min-w-0 flex-col gap-4" aria-label="Graph details">
          <Inspector
            node={selectedNode}
            edge={selectedEdge}
            view={view}
            status={status}
            hits={search.hits}
            blocked={blocked || busy !== null}
            atCap={atCap}
            expanded={selectedNode ? view.expanded.includes(selectedNode.id) : false}
            pathFrom={path.from}
            pathTo={path.to}
            onExpand={expand}
            onExplore={(articleId, title) => explore(articleId, options, title)}
            onSelect={select}
            onPathEnd={(end, articleId) => setPath((p) => ({ ...p, [end]: articleId, status: "idle", result: null, problem: null }))}
          />
          <PathPanel
            path={path}
            view={view}
            blocked={blocked || busy !== null}
            onChange={(next) => setPath((p) => ({ ...p, ...next, status: "idle", result: null, problem: null }))}
            onRun={() => path.from !== null && path.to !== null && runPath(path.from, path.to, path.directed)}
            onClear={() => setPath({ from: null, to: null, directed: true, status: "idle", result: null, problem: null })}
            onSelect={select}
          />
          <SearchHighlight
            search={search}
            view={view}
            onChange={(next) => setSearch((s) => ({ ...s, ...next }))}
            onRun={() => runSearch(search.query, search.method)}
            onClear={() => setSearch((s) => ({ ...s, status: "idle", hits: [], ran: null, message: null }))}
            onSelect={select}
            onExplore={(articleId, title) => explore(articleId, options, title)}
          />
        </aside>
      </div>
    </div>
  );
}

function ProblemBanner({ problem, onRetry, retryLabel = "Retry" }: { problem: GraphProblem; onRetry: () => void; retryLabel?: string }) {
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-[var(--radius-card)] border border-danger/40 bg-danger-tint p-4">
      <p className="font-medium text-ink">{problem.title}</p>
      <p className="text-sm text-ink/85">{problem.message}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={smallButton} onClick={onRetry}>{retryLabel}</button>
        <Link href="/" className={smallButton}>Go to Search</Link>
        <Link href="/library" className={smallButton}>Go to Library</Link>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted" aria-label="Legend">
      <li className="flex items-center gap-1.5"><span aria-hidden className="h-0.5 w-6 bg-[#4d6b8c]" />→ article links to article (real Wikipedia link)</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="w-6 border-t border-dashed border-amber" />article in category</li>
      <li className="flex items-center gap-1.5"><Chip tone="accent">Seed</Chip></li>
      <li className="flex items-center gap-1.5"><span className="rounded bg-source px-1.5 font-mono text-[10px] font-semibold text-page">SOURCE #n</span> retrieved by the search</li>
      <li>Thicker borders = more connections in this view (not global importance)</li>
    </ul>
  );
}
