// node --test: deterministic layout, bounded merges, and degree for the graph explorer.
import assert from "node:assert/strict";
import { test } from "node:test";

import { graphProblem, versionChanged } from "./errors.ts";
import {
  LIMITS, NODE_SIZE, VersionMismatch, addPath, combineNeighborhoods, pushHistory, withoutMaintenance, expandView, isMaintenanceCategory, neighborhoodOf,
  viewDegree, viewFromNeighborhood, visibleGraph, type GNode, type GraphView, type Neighborhood,
} from "./model.ts";

const article = (n: number, depth = 1): GNode => ({
  id: `article:${n}`, kind: "article", article_id: n, title: `Article ${n}`, source_url: `https://en.wikipedia.org/wiki/A${n}`, revision_id: 1, depth,
});
const category = (name: string): GNode => ({ id: `category:${name}`, kind: "category", name, depth: 1 });
const link = (a: number, b: number) => ({ source: `article:${a}`, type: "LINKS_TO" as const, target: `article:${b}` });

function neighborhood(seed: number, nodes: GNode[], edges: Neighborhood["edges"], extra: Partial<Neighborhood> = {}): Neighborhood {
  return { seed: `article:${seed}`, graph_version: "corpus:2", hops: 1, rel_types: ["IN_CATEGORY", "LINKS_TO"], truncated: false, nodes, edges, ...extra };
}

/** 100 articles, 200 links: a ring, chords, and back-links, so it is dense and cyclic. */
function dense(): Neighborhood {
  const nodes = Array.from({ length: 100 }, (_, i) => article(i + 1, i === 0 ? 0 : i < 40 ? 1 : 2));
  const edges = [];
  for (let i = 1; i <= 100; i++) edges.push(link(i, (i % 100) + 1));
  for (let i = 1; i <= 100; i++) edges.push(link(i, ((i + 36) % 100) + 1));
  return neighborhood(1, nodes, edges, { hops: 2 });
}

function assertNoOverlap(view: GraphView) {
  const boxes = view.nodes.map((n) => ({ id: n.id, ...view.positions[n.id], ...NODE_SIZE[n.kind] }));
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      const apart = Math.abs(a.x - b.x) * 2 >= a.width + b.width || Math.abs(a.y - b.y) * 2 >= a.height + b.height;
      assert.ok(apart, `${a.id} overlaps ${b.id}`);
    }
  }
}

test("dense cyclic graph at the 100/200 cap lays out without overlaps", () => {
  const view = viewFromNeighborhood(dense());
  assert.equal(view.nodes.length, 100);
  assert.equal(view.edges.length, 200);
  assert.equal(view.truncated, false);
  assert.deepEqual(view.positions["article:1"], { x: 0, y: 0 });
  assert.equal(Object.keys(view.positions).length, 100);
  assertNoOverlap(view);
});

test("layout is deterministic and independent of response order", () => {
  const nb = dense();
  const a = viewFromNeighborhood(nb).positions;
  const shuffled = { ...nb, nodes: [nb.nodes[0], ...nb.nodes.slice(1).reverse()], edges: [...nb.edges].reverse() };
  assert.deepEqual(viewFromNeighborhood(shuffled).positions, a);
  assert.deepEqual(viewFromNeighborhood(nb).positions, a);
});

test("disconnected seed renders alone and categories get distinct sizes", () => {
  const lone = viewFromNeighborhood(neighborhood(7, [article(7, 0)], []));
  assert.deepEqual(lone.nodes.map((n) => n.id), ["article:7"]);
  assert.equal(lone.edges.length, 0);
  assert.deepEqual(lone.positions["article:7"], { x: 0, y: 0 });

  const withCats = viewFromNeighborhood(neighborhood(7, [article(7, 0), category("Machine learning"), category("Statistics")], [
    { source: "article:7", type: "IN_CATEGORY", target: "category:Machine learning" },
    { source: "article:7", type: "IN_CATEGORY", target: "category:Statistics" },
  ]));
  assertNoOverlap(withCats);
});

test("expansion keeps existing positions and places new nodes without overlap", () => {
  const first = viewFromNeighborhood(neighborhood(1, [article(1, 0), article(2), article(3)], [link(1, 2), link(3, 1)]));
  const { view, added } = expandView(first, "article:2", neighborhood(2, [article(2, 0), article(1), article(4), article(5)], [link(2, 4), link(5, 2), link(1, 2)]));
  for (const id of ["article:1", "article:2", "article:3"]) assert.deepEqual(view.positions[id], first.positions[id]);
  assert.deepEqual(added, ["article:4", "article:5"]);
  assert.equal(view.edges.length, 4); // 1→2 is not duplicated
  assert.deepEqual(view.expanded, ["article:1", "article:2"]);
  assertNoOverlap(view);
});

test("expansion respects the 100-node / 200-edge view cap and marks truncation", () => {
  const nodes = [article(1, 0), ...Array.from({ length: 79 }, (_, i) => article(i + 2))];
  const start = viewFromNeighborhood(neighborhood(1, nodes, nodes.slice(1).map((n) => link(1, Number(n.id.split(":")[1])))));
  assert.equal(start.nodes.length, 80);
  const more = [article(2, 0), ...Array.from({ length: 50 }, (_, i) => article(500 + i))];
  const { view, dropped } = expandView(start, "article:2", neighborhood(2, more, more.slice(1).map((n) => link(2, Number(n.id.split(":")[1])))));
  assert.equal(view.nodes.length, LIMITS.maxNodes);
  assert.ok(view.edges.length <= LIMITS.maxEdges);
  assert.ok(dropped > 0);
  assert.equal(view.truncated, true);
  assert.ok(view.edges.every((e) => view.positions[e.source] && view.positions[e.target]), "edges only between visible nodes");
  assertNoOverlap(view);
});

test("API truncation is carried into the view", () => {
  const view = viewFromNeighborhood(neighborhood(1, [article(1, 0)], [], { truncated: true }));
  assert.equal(view.truncated, true);
});

test("a response from another graph version is refused", () => {
  const view = viewFromNeighborhood(neighborhood(1, [article(1, 0)], []));
  assert.throws(() => expandView(view, "article:1", neighborhood(1, [article(1, 0), article(9)], [link(1, 9)], { graph_version: "corpus:3" })), VersionMismatch);
});

test("path articles are added beside their predecessors", () => {
  const start = viewFromNeighborhood(neighborhood(1, [article(1, 0), article(2)], [link(1, 2)]));
  const { view, added } = addPath(start, {
    graph_version: "corpus:2", found: true,
    nodes: [article(1), article(2), article(30), article(40)] as never,
    edges: [link(1, 2), link(2, 30), link(30, 40)],
  });
  assert.deepEqual(added, ["article:30", "article:40"]);
  assert.deepEqual(view.positions["article:1"], start.positions["article:1"]);
  assert.equal(view.edges.length, 3);
  assertNoOverlap(view);
});

test("degree counts connections in the visible view only", () => {
  const view = viewFromNeighborhood(neighborhood(1, [article(1, 0), article(2), category("Articles with short description")], [
    link(1, 2), link(2, 1), { source: "article:1", type: "IN_CATEGORY", target: "category:Articles with short description" },
  ]));
  assert.equal(viewDegree(view.edges).get("article:1"), 3);
  const shown = visibleGraph(view, { hideMaintenance: true });
  assert.equal(shown.hidden, 1);
  assert.equal(viewDegree(shown.edges).get("article:1"), 2);
  assert.deepEqual([...neighborhoodOf("article:2", shown.edges)].sort(), ["article:1", "article:2"]);
});

test("maintenance category heuristic", () => {
  for (const name of ["Articles with short description", "All articles needing additional references", "Articles with unsourced statements from July 2009", "CS1 errors: missing periodical", "Webarchive template wayback links", "Short description matches Wikidata", "Use dmy dates from August 2021", "Commons category link from Wikidata"]) {
    assert.ok(isMaintenanceCategory(name), name);
  }
  for (const name of ["Machine learning", "Artificial neural networks", "Statistics", "Metrology", "Classification algorithms"]) {
    assert.ok(!isMaintenanceCategory(name), name);
  }
});

test("graph errors map to honest states", () => {
  const graph = { status: "stale" as const, source_version: "corpus:3", imported_version: "corpus:2", imported_at: null, counts: null, detail: null };
  const stale = graphProblem(409, { error: "graph_stale", message: "x", graph });
  assert.equal(stale.kind, "stale");
  assert.ok(stale.blocksTraversal);
  assert.match(stale.message, /corpus:2.*corpus:3/);
  assert.equal(graphProblem(503, { error: "graph_unavailable", message: "The graph service is unavailable." }).kind, "unavailable");
  const timeout = graphProblem(504, { error: "graph_timeout", message: "x" });
  assert.equal(timeout.kind, "timeout");
  assert.equal(timeout.blocksTraversal, false);
  assert.equal(graphProblem(null, null).kind, "unreachable");
  assert.equal(graphProblem(404, { error: "not_found", message: "x" }).kind, "not_found");
  assert.equal(versionChanged("corpus:2", "corpus:3").kind, "version_changed");
});

test("categories fetched separately are merged topical-first", () => {
  const links = neighborhood(1, [article(1, 0), article(2)], [link(1, 2)], { rel_types: ["LINKS_TO"] });
  const cats = neighborhood(1, [article(1, 0), category("All articles needing examples"), category("Deep learning")], [
    { source: "article:1", type: "IN_CATEGORY", target: "category:All articles needing examples" },
    { source: "article:1", type: "IN_CATEGORY", target: "category:Deep learning" },
  ], { rel_types: ["IN_CATEGORY"], truncated: true });
  const combined = combineNeighborhoods(links, cats);
  assert.deepEqual(combined.nodes.map((n) => n.id), ["article:1", "article:2", "category:Deep learning", "category:All articles needing examples"]);
  assert.deepEqual(combined.rel_types, ["IN_CATEGORY", "LINKS_TO"]);
  assert.equal(combined.truncated, true);
  assert.equal(combined.edges.length, 3);
  assert.equal(combineNeighborhoods(links, null), links);
  const topical = combineNeighborhoods(links, withoutMaintenance(cats));
  assert.deepEqual(topical.nodes.map((n) => n.id), ["article:1", "article:2", "category:Deep learning"]);
  assert.equal(topical.edges.length, 2);
  assert.throws(() => combineNeighborhoods(links, { ...cats, graph_version: "corpus:9" }), VersionMismatch);
});

test("a path between nodes already in view still adds its missing links", () => {
  // 1 and 3 came from different expansions; the 2→3 link was never fetched.
  const start = viewFromNeighborhood(neighborhood(1, [article(1, 0), article(2), article(3)], [link(1, 2)]));
  const { view, added, dropped } = addPath(start, {
    graph_version: "corpus:2", found: true, nodes: [article(1), article(2), article(3)] as never, edges: [link(1, 2), link(2, 3)],
  });
  assert.deepEqual(added, []);
  assert.equal(dropped, 0);
  assert.equal(view.edges.length, start.edges.length + 1);
  assert.ok(view.edges.some((e) => e.id === "article:2|LINKS_TO|article:3"));
});

test("history trimming keeps the first (seed) entry", () => {
  let h = [0];
  for (let i = 1; i <= 40; i++) h = pushHistory(h, i, 30);
  assert.equal(h.length, 30);
  assert.equal(h[0], 0);
  assert.deepEqual(h.slice(1, 3), [12, 13]);
  assert.equal(h.at(-1), 40);
  assert.deepEqual(pushHistory([0, 1], 2, 30), [0, 1, 2]);
});
