"""Import a MariaDB snapshot into Neo4j and report graph status.

Strategy: explicit rebuild in place. The import marks the graph `rebuilding`, upserts every
node/edge in idempotent batches stamped with a fresh import ID, deletes CiteHop-managed
nodes/edges that carry an older stamp, validates the result against the snapshot, and only
then records the corpus version as complete. An interrupted or invalid import leaves the
graph `rebuilding`, never current. Neo4j and MariaDB are not updated atomically together.

Everything written here carries the `CiteHop` label; nothing outside that namespace is
matched, changed, or deleted.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from neo4j import Query, RoutingControl
from neo4j.exceptions import DriverError, Neo4jError

from citehop.graph.source import Snapshot

META_KEY = "graph"
DEFAULT_TIMEOUT_S = 5.0

CONSTRAINTS = (
    # Only CiteHop-labelled nodes are constrained, so other data in a shared Neo4j is never
    # affected. `uid` encodes kind + stable ID, which makes it unique per article and category.
    "CREATE CONSTRAINT citehop_uid IF NOT EXISTS FOR (n:CiteHop) REQUIRE n.uid IS UNIQUE",
    "CREATE CONSTRAINT citehop_meta_key IF NOT EXISTS "
    "FOR (m:CiteHopGraphMeta) REQUIRE m.key IS UNIQUE",
)

MARK_REBUILDING = """
MERGE (m:CiteHopGraphMeta {key: $key})
SET m.state = 'rebuilding', m.import_id = $import_id, m.target_version = $version,
    m.started_at = $now, m.last_error = null
"""

MARK_FAILED = """
MATCH (m:CiteHopGraphMeta {key: $key, import_id: $import_id})
SET m.last_error = $error
"""

MARK_COMPLETE = """
MATCH (m:CiteHopGraphMeta {key: $key, import_id: $import_id})
SET m.state = 'complete', m.imported_version = $version, m.imported_at = $now,
    m.articles = $articles, m.categories = $categories,
    m.links = $links, m.memberships = $memberships
"""

UPSERT_ARTICLES = """
UNWIND $rows AS row
MERGE (a:CiteHop {uid: row.uid})
SET a:Article, a.article_id = row.article_id, a.title = row.title, a.source_url = row.source_url,
    a.revision_id = row.revision_id, a.import_id = $import_id
"""

UPSERT_CATEGORIES = """
UNWIND $rows AS row
MERGE (c:CiteHop {uid: row.uid})
SET c:Category, c.name = row.name, c.import_id = $import_id
"""

UPSERT_MEMBERSHIPS = """
UNWIND $rows AS row
MATCH (a:CiteHop:Article {uid: row.article_uid})
MATCH (c:CiteHop:Category {uid: row.category_uid})
MERGE (a)-[r:IN_CATEGORY]->(c)
SET r.import_id = $import_id
"""

UPSERT_LINKS = """
UNWIND $rows AS row
MATCH (a:CiteHop:Article {uid: row.source})
MATCH (b:CiteHop:Article {uid: row.target})
MERGE (a)-[r:LINKS_TO]->(b)
SET r.import_id = $import_id
"""

DELETE_OLD_EDGES = """
MATCH (:CiteHop)-[r:LINKS_TO|IN_CATEGORY]->(:CiteHop)
WHERE coalesce(r.import_id, '') <> $import_id
WITH r LIMIT $batch
DELETE r
RETURN count(*) AS deleted
"""

DELETE_OLD_NODES = """
MATCH (n:CiteHop)
WHERE (n:Article OR n:Category) AND coalesce(n.import_id, '') <> $import_id
WITH n LIMIT $batch
DETACH DELETE n
RETURN count(*) AS deleted
"""

READ_ARTICLES = "MATCH (a:CiteHop:Article) RETURN a.article_id AS id, a.revision_id AS rev"
READ_CATEGORIES = "MATCH (c:CiteHop:Category) RETURN c.name AS name"
READ_LINKS = """
MATCH (a:CiteHop:Article)-[:LINKS_TO]->(b:CiteHop:Article)
RETURN a.article_id AS source, b.article_id AS target
"""
READ_MEMBERSHIPS = """
MATCH (a:CiteHop:Article)-[:IN_CATEGORY]->(c:CiteHop:Category)
RETURN a.article_id AS article_id, c.name AS category
"""
READ_EDGE_COUNT = "MATCH (:CiteHop)-[r:LINKS_TO|IN_CATEGORY]->(:CiteHop) RETURN count(r) AS n"

READ_META = "MATCH (m:CiteHopGraphMeta {key: $key}) RETURN m {.*} AS meta"


class GraphError(Exception):
    """Base class for graph adapter errors."""


class GraphUnavailable(GraphError):
    """Neo4j cannot be reached or rejected the connection."""


class GraphTimeout(GraphError):
    """A graph query exceeded its transaction timeout."""


class GraphNotReady(GraphError):
    """The graph is stale, rebuilding, or never imported; traversal is disabled."""

    def __init__(self, status: GraphStatus):
        super().__init__(f"graph is {status.status}: {status.detail}")
        self.status = status


class GraphNotFound(GraphError):
    """A requested article is not in the imported graph."""


class ImportValidationError(GraphError):
    """The imported graph does not match the MariaDB snapshot."""


def article_uid(article_id) -> str:
    return f"article:{article_id}"


def category_uid(name: str) -> str:
    return f"category:{name}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def run(driver, cypher: str, params=None, *, write=False, timeout=None, database=None):
    """Run one parameterized statement in its own managed transaction with a timeout."""
    try:
        return driver.execute_query(
            Query(cypher, timeout=timeout),
            params or {},
            routing_=RoutingControl.WRITE if write else RoutingControl.READ,
            database_=database,
        ).records
    except Neo4jError as exc:
        code = exc.code or ""
        if "TransactionTimedOut" in code:
            raise GraphTimeout(f"graph query exceeded {timeout}s") from exc
        # Not reachable/usable right now: auth, missing or starting database, transient faults.
        if code.startswith(("Neo.ClientError.Security", "Neo.ClientError.Database",
                            "Neo.TransientError")):
            raise GraphUnavailable(str(exc)) from exc
        raise
    except DriverError as exc:
        raise GraphUnavailable(str(exc)) from exc


def ensure_constraints(driver, database=None) -> None:
    for statement in CONSTRAINTS:
        run(driver, statement, write=True, database=database)


def _batches(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _write_batches(driver, cypher, rows, import_id, batch_size, database):
    for batch in _batches(rows, batch_size):
        run(driver, cypher, {"rows": batch, "import_id": import_id}, write=True, database=database)


def _delete_until_empty(driver, cypher, import_id, batch_size, database) -> int:
    total = 0
    while True:
        params = {"import_id": import_id, "batch": batch_size}
        deleted = run(driver, cypher, params, write=True, database=database)[0]["deleted"]
        total += deleted
        if deleted == 0:
            return total


def validate(driver, snapshot: Snapshot, database=None) -> list[str]:
    """Compare the CiteHop namespace with the snapshot exactly; return mismatch descriptions."""
    problems = []
    articles = {(r["id"], r["rev"]) for r in run(driver, READ_ARTICLES, database=database)}
    expected_articles = {(a.article_id, a.revision_id) for a in snapshot.articles}
    categories = {r["name"] for r in run(driver, READ_CATEGORIES, database=database)}
    links = [(r["source"], r["target"]) for r in run(driver, READ_LINKS, database=database)]
    memberships = [
        (r["article_id"], r["category"]) for r in run(driver, READ_MEMBERSHIPS, database=database)
    ]
    edge_count = run(driver, READ_EDGE_COUNT, database=database)[0]["n"]
    checks = (
        ("articles", articles, expected_articles),
        ("categories", categories, set(snapshot.categories)),
        ("links", set(links), set(snapshot.links)),
        ("memberships", set(memberships), set(snapshot.memberships)),
    )
    for name, actual, expected in checks:
        if actual != expected:
            problems.append(
                f"{name}: {len(actual - expected)} unexpected, {len(expected - actual)} missing"
            )
    if len(links) != len(set(links)) or len(memberships) != len(set(memberships)):
        problems.append("duplicate edges present")
    if edge_count != len(links) + len(memberships):
        problems.append("namespace edges are not all between Article/Category nodes")
    return problems


@dataclass(frozen=True)
class ImportResult:
    version: str
    import_id: str
    counts: dict[str, int]
    deleted_edges: int
    deleted_nodes: int
    skipped_links: int
    skipped_memberships: int


def import_snapshot(driver, snapshot: Snapshot, *, batch_size=500, database=None) -> ImportResult:
    """Rebuild the CiteHop graph from `snapshot`. Marks complete only after validation."""
    ensure_constraints(driver, database)
    import_id = uuid.uuid4().hex
    version = snapshot.version
    base = {"key": META_KEY, "import_id": import_id}
    run(driver, MARK_REBUILDING, {**base, "version": version, "now": _now()},
        write=True, database=database)
    try:
        articles = [
            {"uid": article_uid(a.article_id), **asdict(a)} for a in snapshot.articles
        ]
        categories = [{"uid": category_uid(n), "name": n} for n in snapshot.categories]
        memberships = [
            {"article_uid": article_uid(a), "category_uid": category_uid(c)}
            for a, c in snapshot.memberships
        ]
        links = [{"source": article_uid(s), "target": article_uid(t)} for s, t in snapshot.links]
        _write_batches(driver, UPSERT_ARTICLES, articles, import_id, batch_size, database)
        _write_batches(driver, UPSERT_CATEGORIES, categories, import_id, batch_size, database)
        _write_batches(driver, UPSERT_MEMBERSHIPS, memberships, import_id, batch_size, database)
        _write_batches(driver, UPSERT_LINKS, links, import_id, batch_size, database)
        deleted_edges = _delete_until_empty(
            driver, DELETE_OLD_EDGES, import_id, batch_size, database
        )
        deleted_nodes = _delete_until_empty(
            driver, DELETE_OLD_NODES, import_id, batch_size, database
        )
        problems = validate(driver, snapshot, database)
        if problems:
            raise ImportValidationError("; ".join(problems))
    except Exception as exc:
        try:
            run(driver, MARK_FAILED, {**base, "error": f"{type(exc).__name__}: {exc}"[:500]},
                write=True, database=database)
        except GraphError:
            pass  # Neo4j went away; the marker already says rebuilding.
        raise
    counts = snapshot.counts()
    run(driver, MARK_COMPLETE, {**base, "version": version, "now": _now(), **counts},
        write=True, database=database)
    return ImportResult(
        version=version,
        import_id=import_id,
        counts=counts,
        deleted_edges=deleted_edges,
        deleted_nodes=deleted_nodes,
        skipped_links=snapshot.skipped_links,
        skipped_memberships=snapshot.skipped_memberships,
    )


@dataclass(frozen=True)
class GraphStatus:
    status: str  # ready | stale | rebuilding | unavailable
    source_version: str | None
    imported_version: str | None
    imported_at: str | None
    counts: dict[str, int] | None
    detail: str | None = None


def graph_status(driver, source_version: str | None, *, timeout=DEFAULT_TIMEOUT_S,
                 database=None) -> GraphStatus:
    """Status of the CiteHop graph. `source_version` is None when MariaDB could not be read."""
    try:
        rows = run(driver, READ_META, {"key": META_KEY}, timeout=timeout, database=database)
    except (GraphError, Neo4jError) as exc:  # status reports problems; it never raises them
        return GraphStatus("unavailable", source_version, None, None, None, str(exc))
    if not rows:
        return GraphStatus("unavailable", source_version, None, None, None, "graph never imported")
    meta = rows[0]["meta"]
    imported = meta.get("imported_version")
    counts = None
    if imported:
        counts = {k: meta.get(k) for k in ("articles", "categories", "links", "memberships")}
    if meta.get("state") != "complete":
        detail = "import in progress or interrupted; rerun the import"
        if meta.get("last_error"):
            detail = f"last import failed ({meta['last_error']}); rerun the import"
        return GraphStatus("rebuilding", source_version, None, None, None, detail)
    common = (source_version, imported, meta.get("imported_at"), counts)
    if source_version is None:
        return GraphStatus("stale", *common, "MariaDB source version unavailable")
    if source_version != imported:
        return GraphStatus("stale", *common, "MariaDB corpus changed; rerun the import")
    return GraphStatus("ready", *common)
