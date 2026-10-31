// Pure graph-view model for the C12 explorer: merging bounded API responses, the
// deterministic radial layout, visible degree, and view filters. No React or browser
// APIs, so it runs under `node --test` and every result is reproducible.
import type { Schemas } from "@/lib/api/client";

export type ArticleNode = Schemas["ArticleNode"];
export type CategoryNode = Schemas["CategoryNode"];
export type GNode = ArticleNode | CategoryNode;
export type RelType = Schemas["GraphEdge"]["type"];
export type GEdge = Schemas["GraphEdge"] & { id: string };
export type Pos = { x: number; y: number };

// Mirrors citehop/graph/queries.py and docs/ARCHITECTURE.md "Graph query limits".
export const LIMITS = { defaultNodes: 50, defaultEdges: 100, maxNodes: 100, maxEdges: 200, maxPathLinks: 3 } as const;
export const REL_TYPES: RelType[] = ["LINKS_TO", "IN_CATEGORY"];

export const NODE_SIZE = { article: { width: 188, height: 64 }, category: { width: 168, height: 40 } } as const;

export type GraphView = {
  seed: string; // node id of the exploration seed
  graphVersion: string; // imported snapshot every node/edge came from
  hops: 1 | 2;
  relTypes: RelType[];
  nodes: GNode[]; // insertion order is deterministic (API order)
  edges: GEdge[];
  positions: Record<string, Pos>;
  truncated: boolean; // the API cut a response, or the 100/200 view cap dropped elements
  expanded: string[]; // node ids whose neighborhood was merged in
};

export type Neighborhood = Pick<Schemas["Neighborhood"], "seed" | "graph_version" | "hops" | "rel_types" | "truncated" | "nodes" | "edges">;
export type PathResult = Pick<Schemas["GraphPath"], "graph_version" | "found" | "nodes" | "edges">;

export const edgeId = (e: Schemas["GraphEdge"]) => `${e.source}|${e.type}|${e.target}`;
export const nodeLabel = (n: GNode) => (n.kind === "article" ? n.title : n.name);

/** A fresh view from one neighborhood response, laid out radially around its seed. */
export function viewFromNeighborhood(nb: Neighborhood): GraphView {
  const nodes = nb.nodes.slice(0, LIMITS.maxNodes);
  const ids = new Set(nodes.map((n) => n.id));
  const edges = nb.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .slice(0, LIMITS.maxEdges)
    .map((e) => ({ ...e, id: edgeId(e) }));
  const view: GraphView = {
    seed: nb.seed,
    graphVersion: nb.graph_version,
    hops: nb.hops === 2 ? 2 : 1,
    relTypes: [...nb.rel_types],
    nodes,
    edges,
    positions: {},
    truncated: nb.truncated || nodes.length < nb.nodes.length || edges.length < nb.edges.length,
    expanded: [nb.seed],
  };
  return { ...view, positions: radialLayout(view) };
}

export class VersionMismatch extends Error {
  expected: string;
  received: string;
  constructor(expected: string, received: string) {
    super(`graph version changed from ${expected} to ${received}`);
    this.expected = expected;
    this.received = received;
  }
}

type Merge = { view: GraphView; added: string[]; dropped: number };

/**
 * Adds new nodes/edges in API order while the whole view stays within 100 nodes / 200
 * edges. Existing positions never move; added nodes are placed around `anchor`.
 */
function mergeInto(view: GraphView, nodes: GNode[], edges: Schemas["GraphEdge"][], version: string, anchor: string | ((id: string, positions: Record<string, Pos>) => string)): Merge {
  if (version !== view.graphVersion) throw new VersionMismatch(view.graphVersion, version);
  const have = new Set(view.nodes.map((n) => n.id));
  const fresh = nodes.filter((n) => !have.has(n.id));
  const room = Math.max(0, LIMITS.maxNodes - view.nodes.length);
  const added = fresh.slice(0, room);
  const ids = new Set([...have, ...added.map((n) => n.id)]);
  const haveEdges = new Set(view.edges.map((e) => e.id));
  const newEdges = edges
    .map((e) => ({ ...e, id: edgeId(e) }))
    .filter((e) => !haveEdges.has(e.id) && ids.has(e.source) && ids.has(e.target));
  const edgeRoom = Math.max(0, LIMITS.maxEdges - view.edges.length);
  const keptEdges = newEdges.slice(0, edgeRoom);
  const dropped = fresh.length - added.length + newEdges.length - keptEdges.length;

  const next: GraphView = { ...view, nodes: [...view.nodes, ...added], edges: [...view.edges, ...keptEdges] };
  const positions = { ...view.positions };
  for (const node of added) {
    const parent = typeof anchor === "string" ? anchor : anchor(node.id, positions);
    positions[node.id] = placeNear(node, parent, next, positions);
  }
  return { view: { ...next, positions, truncated: view.truncated || dropped > 0 }, added: added.map((n) => n.id), dropped };
}

/** Merge a neighborhood fetched for `parent` (expansion). */
export function expandView(view: GraphView, parent: string, nb: Neighborhood): Merge {
  const merged = mergeInto(view, nb.nodes, nb.edges, nb.graph_version, parent);
  const expanded = view.expanded.includes(parent) ? view.expanded : [...view.expanded, parent];
  return { ...merged, view: { ...merged.view, truncated: merged.view.truncated || nb.truncated, expanded } };
}

/** Merge a path's articles and links; each missing article is placed next to its predecessor. */
export function addPath(view: GraphView, path: PathResult): Merge {
  const order = path.nodes.map((n) => n.id);
  const anchor = (id: string, positions: Record<string, Pos>) => {
    const i = order.indexOf(id);
    for (let j = i - 1; j >= 0; j--) if (order[j] in positions) return order[j];
    return order.slice(i + 1).find((other) => other in positions) ?? view.seed;
  };
  return mergeInto(view, path.nodes, path.edges, path.graph_version, anchor);
}

/**
 * One exploration step = an article-link neighborhood plus the article's own categories,
 * fetched separately. A combined fetch fills the leftover node budget with categories in
 * name order, which puts Wikipedia housekeeping categories ("All articles…") first.
 * Topical categories are listed before maintenance ones so caps drop the latter first.
 */
export function combineNeighborhoods(links: Neighborhood, categories: Neighborhood | null): Neighborhood {
  if (!categories) return links;
  if (categories.graph_version !== links.graph_version) throw new VersionMismatch(links.graph_version, categories.graph_version);
  const have = new Set(links.nodes.map((n) => n.id));
  const extra = categories.nodes
    .filter((n) => !have.has(n.id))
    .sort((a, b) => Number(a.kind === "category" && isMaintenanceCategory(a.name)) - Number(b.kind === "category" && isMaintenanceCategory(b.name)));
  return {
    ...links,
    rel_types: [...new Set([...links.rel_types, ...categories.rel_types])].sort(),
    truncated: links.truncated || categories.truncated,
    nodes: [...links.nodes, ...extra],
    edges: [...links.edges, ...categories.edges],
  };
}

/** Append to a bounded history, always keeping the first entry (the seed view Reset returns to). */
export function pushHistory<T>(history: T[], entry: T, limit: number): T[] {
  const next = [...history, entry];
  return next.length <= limit ? next : [next[0], ...next.slice(next.length - (limit - 1))];
}

// --- view filters and degree --------------------------------------------------------------

const MAINTENANCE = [
  /^(all )?articles? (with|needing|containing|lacking|using|that|to be|from|which|prone)\b/i,
  /^all (articles|pages|wikipedia)\b/i,
  /^(wikipedia|cs1|pages|webarchive|use (dmy|mdy) dates|short description|commons category|harv and sfn|good articles|featured articles)\b/i,
  /\b(articles|pages|statements) (with|needing|from)\b/i,
  /\bfrom (january|february|march|april|may|june|july|august|september|october|november|december) \d{4}$/i,
];

/** Wikipedia housekeeping categories (C02 does not keep the `hidden` flag yet; see docs/GRAPH.md). */
export function isMaintenanceCategory(name: string): boolean {
  return MAINTENANCE.some((pattern) => pattern.test(name));
}

/** Drop housekeeping category nodes (and their edges) from a response before merging. */
export function withoutMaintenance(nb: Neighborhood): Neighborhood {
  const nodes = nb.nodes.filter((n) => !(n.kind === "category" && isMaintenanceCategory(n.name)));
  const ids = new Set(nodes.map((n) => n.id));
  return { ...nb, nodes, edges: nb.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
}

export type ViewFilter = { hideMaintenance: boolean };

export function visibleGraph(view: GraphView, filter: ViewFilter) {
  const nodes = view.nodes.filter((n) => !(filter.hideMaintenance && n.kind === "category" && isMaintenanceCategory(n.name)));
  const ids = new Set(nodes.map((n) => n.id));
  const edges = view.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  return { nodes, edges, hidden: view.nodes.length - nodes.length };
}

/** Edges touching each node among the given (visible) edges: "connections in this view". */
export function viewDegree(edges: GEdge[]): Map<string, number> {
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  return degree;
}

export function degreeTier(degree: number): 0 | 1 | 2 {
  return degree >= 8 ? 2 : degree >= 3 ? 1 : 0;
}

/** Ids of a node and everything one visible edge away. */
export function neighborhoodOf(id: string, edges: GEdge[]): Set<string> {
  const out = new Set([id]);
  for (const e of edges) {
    if (e.source === id) out.add(e.target);
    if (e.target === id) out.add(e.source);
  }
  return out;
}

// --- deterministic layout -----------------------------------------------------------------

// Rings are ellipses (wider than tall) because the cards are; ASPECT keeps left/right
// neighbors on adjacent rings from overlapping. SPACING is the minimum gap along a ring.
const ASPECT = 1.9;
const FIRST_RING = 210;
const RING_STEP = 100;
const SPACING = 112;
const MARGIN = 14;

const sizeOf = (n: GNode) => NODE_SIZE[n.kind];

function overlaps(a: Pos, sa: { width: number; height: number }, b: Pos, sb: { width: number; height: number }) {
  return Math.abs(a.x - b.x) * 2 < sa.width + sb.width + 2 * MARGIN && Math.abs(a.y - b.y) * 2 < sa.height + sb.height + 2 * MARGIN;
}

/** Center positions (React Flow positions are top-left; the canvas converts). */
export function radialLayout(view: Pick<GraphView, "seed" | "nodes" | "edges">): Record<string, Pos> {
  const byId = new Map(view.nodes.map((n) => [n.id, n]));
  const adjacent = new Map<string, string[]>();
  for (const e of view.edges) {
    adjacent.set(e.source, [...(adjacent.get(e.source) ?? []), e.target]);
    adjacent.set(e.target, [...(adjacent.get(e.target) ?? []), e.source]);
  }
  // BFS depth from the seed over visible edges; parents give each node an angular home.
  const depth = new Map<string, number>([[view.seed, 0]]);
  const parent = new Map<string, string>();
  const queue = [view.seed];
  while (queue.length) {
    const id = queue.shift()!;
    const next = [...(adjacent.get(id) ?? [])].sort();
    for (const other of next) {
      if (depth.has(other) || !byId.has(other)) continue;
      depth.set(other, depth.get(id)! + 1);
      parent.set(other, id);
      queue.push(other);
    }
  }
  const unreachable = Math.max(0, ...depth.values()) + 1;
  const rings = new Map<number, GNode[]>();
  for (const n of view.nodes) {
    if (n.id === view.seed) continue;
    const d = depth.get(n.id) ?? unreachable;
    rings.set(d, [...(rings.get(d) ?? []), n]);
  }

  const positions: Record<string, Pos> = {};
  const angle = new Map<string, number>();
  const placed: { pos: Pos; size: { width: number; height: number } }[] = [];
  const put = (n: GNode, pos: Pos) => {
    const size = sizeOf(n);
    while (placed.some((p) => overlaps(pos, size, p.pos, p.size))) {
      const r = Math.hypot(pos.x / ASPECT, pos.y) || 1; // push outward along the same ray
      pos = { x: (pos.x * (r + 24)) / r, y: (pos.y * (r + 24)) / r };
    }
    positions[n.id] = pos;
    placed.push({ pos, size });
  };
  if (byId.has(view.seed)) {
    put(byId.get(view.seed)!, { x: 0, y: 0 });
    angle.set(view.seed, -Math.PI / 2);
  }

  let radius = FIRST_RING - RING_STEP;
  for (const d of [...rings.keys()].sort((a, b) => a - b)) {
    // Articles before categories; deeper rings follow their parent's angle.
    const members = rings.get(d)!.sort((a, b) => {
      const pa = angle.get(parent.get(a.id) ?? "") ?? 0;
      const pb = angle.get(parent.get(b.id) ?? "") ?? 0;
      if (d > 1 && pa !== pb) return pa - pb;
      if (a.kind !== b.kind) return a.kind === "article" ? -1 : 1;
      return nodeLabel(a).localeCompare(nodeLabel(b), "en") || a.id.localeCompare(b.id);
    });
    let i = 0;
    let ring = 0;
    while (i < members.length) {
      radius += RING_STEP;
      const capacity = Math.max(6, Math.floor((2 * Math.PI * radius) / SPACING));
      const batch = members.slice(i, i + capacity);
      const offset = ring % 2 ? Math.PI / batch.length : 0;
      batch.forEach((n, k) => {
        const a = -Math.PI / 2 + offset + (2 * Math.PI * k) / batch.length;
        angle.set(n.id, a);
        put(n, { x: Math.round(Math.cos(a) * radius * ASPECT), y: Math.round(Math.sin(a) * radius) });
      });
      i += batch.length;
      ring += 1;
    }
  }
  return positions;
}

/**
 * First free slot around `parentId`, facing away from the view's center. Slots are tried
 * in a fixed order on growing rings, so the same graph always yields the same placement.
 */
export function placeNear(node: GNode, parentId: string, view: Pick<GraphView, "nodes">, positions: Record<string, Pos>): Pos {
  const sizes = new Map(view.nodes.map((n) => [n.id, sizeOf(n)]));
  const origin = positions[parentId] ?? { x: 0, y: 0 };
  const others = Object.entries(positions);
  const cx = others.reduce((s, [, p]) => s + p.x, 0) / (others.length || 1);
  const cy = others.reduce((s, [, p]) => s + p.y, 0) / (others.length || 1);
  const away = origin.x === cx && origin.y === cy ? -Math.PI / 2 : Math.atan2(origin.y - cy, (origin.x - cx) / ASPECT);
  const size = sizeOf(node);
  for (let ring = 0; ; ring++) {
    const radius = 150 + ring * 80;
    const slots = Math.max(6, Math.floor((2 * Math.PI * radius) / SPACING));
    for (let k = 0; k < slots; k++) {
      const step = Math.ceil(k / 2) * (k % 2 ? 1 : -1); // 0, +1, -1, +2, -2, …
      const a = away + (2 * Math.PI * step) / slots;
      const pos = { x: Math.round(origin.x + Math.cos(a) * radius * ASPECT), y: Math.round(origin.y + Math.sin(a) * radius) };
      if (!others.some(([id, p]) => overlaps(pos, size, p, sizes.get(id) ?? NODE_SIZE.article))) return pos;
    }
  }
}
