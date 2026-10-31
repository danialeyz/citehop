"""Bounded neighborhood and path queries over the imported CiteHop graph.

Bounds are enforced here, not in the renderer: hop count, node and edge caps, per-hop
LIMIT on expansion, and a transaction timeout on every statement. Ordering is by stable
`uid`, so the same request on the same snapshot returns the same truncated result.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from citehop.graph.store import (
    DEFAULT_TIMEOUT_S,
    GraphNotFound,
    GraphNotReady,
    GraphStatus,
    article_uid,
    graph_status,
    run,
)

REL_TYPES = ("LINKS_TO", "IN_CATEGORY")
MAX_HOPS = 2
DEFAULT_NODES, MAX_NODES = 50, 100
DEFAULT_EDGES, MAX_EDGES = 100, 200
# Computing the source version scans MariaDB's graph tables, so a long-lived caller reuses it
# for this long. A corpus change can therefore take up to this long to show as `stale`.
SOURCE_VERSION_TTL_S = 60.0
PATH_MAX_LINKS = 3

FIND_ARTICLES = """
UNWIND $uids AS uid
MATCH (a:CiteHop:Article {uid: uid})
RETURN a {.*} AS props
"""

NEIGHBORS = """
UNWIND $frontier AS fid
MATCH (f:CiteHop {uid: fid})-[r]-(n:CiteHop)
WHERE type(r) IN $types AND NOT n.uid IN $seen
WITH DISTINCT n
ORDER BY n.uid
LIMIT $limit
RETURN n {.*} AS props, n:Article AS is_article
"""

EDGES_AMONG = """
MATCH (a:CiteHop)-[r]->(b:CiteHop)
WHERE a.uid IN $ids AND b.uid IN $ids AND type(r) IN $types
WITH a.uid AS source, type(r) AS type, b.uid AS target
ORDER BY CASE WHEN source = $seed OR target = $seed THEN 0 ELSE 1 END, type, source, target
LIMIT $limit
RETURN source, type, target
"""

# Directed and undirected variants are fixed strings; only values are parameters.
PATH_DIRECTED = """
MATCH (a:CiteHop:Article {uid: $source}), (b:CiteHop:Article {uid: $target})
MATCH p = allShortestPaths((a)-[:LINKS_TO*1..3]->(b))
WHERE all(n IN nodes(p) WHERE n:CiteHop AND n:Article)
WITH p, [n IN nodes(p) | n.uid] AS ids
ORDER BY ids
LIMIT 1
RETURN [n IN nodes(p) | n {.*}] AS nodes,
       [r IN relationships(p) | [startNode(r).uid, endNode(r).uid]] AS edges
"""
PATH_UNDIRECTED = PATH_DIRECTED.replace("*1..3]->(b)", "*1..3]-(b)")


def _article(props, depth=None) -> dict:
    node = {
        "id": props["uid"],
        "kind": "article",
        "article_id": props["article_id"],
        "title": props["title"],
        "source_url": props["source_url"],
        "revision_id": props.get("revision_id"),
    }
    if depth is not None:
        node["depth"] = depth
    return node


def _category(props, depth) -> dict:
    return {"id": props["uid"], "kind": "category", "name": props["name"], "depth": depth}


class GraphQueries:
    """Read-only graph access. `source_version` returns MariaDB's current version or None.

    Create one instance per process and reuse it; the source version is cached for
    `version_ttl` seconds. Failed reads are not cached.
    """

    def __init__(self, driver, source_version: Callable[[], str | None], *,
                 timeout=DEFAULT_TIMEOUT_S, database=None, version_ttl=SOURCE_VERSION_TTL_S):
        self.driver = driver
        self.source_version = source_version
        self.timeout = timeout
        self.database = database
        self.version_ttl = version_ttl
        self._version: tuple[float, str] | None = None

    def _source_version(self) -> str | None:
        now = time.monotonic()
        if self._version and now - self._version[0] < self.version_ttl:
            return self._version[1]
        try:
            version = self.source_version()
        except Exception:  # MariaDB down: report stale, never block on it
            return None
        self._version = (now, version) if version else None
        return version

    def _read(self, cypher, params):
        return run(self.driver, cypher, params, timeout=self.timeout, database=self.database)

    def status(self) -> GraphStatus:
        return graph_status(self.driver, self._source_version(), timeout=self.timeout,
                            database=self.database)

    def _require_ready(self) -> GraphStatus:
        status = self.status()
        if status.status != "ready":
            raise GraphNotReady(status)
        return status

    def _articles(self, ids) -> dict:
        rows = self._read(FIND_ARTICLES, {"uids": [article_uid(i) for i in ids]})
        return {r["props"]["article_id"]: r["props"] for r in rows}

    def neighborhood(self, article_id, *, hops=1, max_nodes=DEFAULT_NODES,
                     max_edges=DEFAULT_EDGES, rel_types=REL_TYPES) -> dict:
        types = sorted(set(rel_types))
        if not 1 <= hops <= MAX_HOPS:
            raise ValueError(f"hops must be 1..{MAX_HOPS}")
        if not 1 <= max_nodes <= MAX_NODES:
            raise ValueError(f"max_nodes must be 1..{MAX_NODES}")
        if not 1 <= max_edges <= MAX_EDGES:
            raise ValueError(f"max_edges must be 1..{MAX_EDGES}")
        if not types or not set(types) <= set(REL_TYPES):
            raise ValueError(f"rel_types must be a non-empty subset of {REL_TYPES}")
        status = self._require_ready()

        found = self._articles([article_id])
        if article_id not in found:
            raise GraphNotFound(f"article {article_id!r} is not in the graph")
        seed = _article(found[article_id], depth=0)
        nodes, frontier, truncated = [seed], [seed["id"]], False
        for depth in range(1, hops + 1):
            remaining = max_nodes - len(nodes)
            rows = self._read(NEIGHBORS, {
                "frontier": frontier, "types": types,
                "seen": [n["id"] for n in nodes], "limit": remaining + 1,
            })
            if len(rows) > remaining:
                truncated, rows = True, rows[:remaining]
            added = [
                _article(r["props"], depth) if r["is_article"] else _category(r["props"], depth)
                for r in rows
            ]
            nodes.extend(added)
            frontier = [n["id"] for n in added]
            if not frontier or truncated:
                break

        edges = [
            {"source": r["source"], "type": r["type"], "target": r["target"]}
            for r in self._read(EDGES_AMONG, {
                "ids": [n["id"] for n in nodes], "types": types,
                "seed": seed["id"], "limit": max_edges + 1,
            })
        ]
        if len(edges) > max_edges:
            truncated, edges = True, edges[:max_edges]
        return {
            "seed": seed["id"],
            "graph_version": status.imported_version,
            "hops": hops,
            "rel_types": types,
            "limits": {"max_nodes": max_nodes, "max_edges": max_edges},
            "truncated": truncated,
            "nodes": nodes,
            "edges": edges,
        }

    def path(self, source_id, target_id, *, directed=True) -> dict:
        """Deterministic shortest LINKS_TO path of at most three links. Categories excluded."""
        status = self._require_ready()
        found = self._articles([source_id, target_id])
        missing = [i for i in (source_id, target_id) if i not in found]
        if missing:
            raise GraphNotFound(f"articles not in the graph: {missing!r}")
        result = {
            "source": article_uid(source_id),
            "target": article_uid(target_id),
            "directed": directed,
            "max_links": PATH_MAX_LINKS,
            "graph_version": status.imported_version,
        }
        if source_id == target_id:
            return {**result, "found": True, "nodes": [_article(found[source_id])], "edges": []}
        rows = self._read(PATH_DIRECTED if directed else PATH_UNDIRECTED,
                          {"source": article_uid(source_id), "target": article_uid(target_id)})
        if not rows:
            message = f"No path within {PATH_MAX_LINKS} links"
            return {**result, "found": False, "nodes": [], "edges": [], "message": message}
        return {
            **result,
            "found": True,
            "nodes": [_article(p) for p in rows[0]["nodes"]],
            "edges": [{"source": s, "type": "LINKS_TO", "target": t} for s, t in rows[0]["edges"]],
        }
