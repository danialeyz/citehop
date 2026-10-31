"""Graph import/query tests against a real, disposable Neo4j.

Set CITEHOP_TEST_NEO4J_URI (and _USER/_PASSWORD) to a throwaway instance; the tests clear the
CiteHop namespace there. Run with: pytest -m neo4j
"""

import os

import pytest
from neo4j import GraphDatabase

from citehop.graph import store
from citehop.graph.queries import GraphQueries
from citehop.graph.source import build_snapshot
from citehop.graph.store import (
    GraphNotFound,
    GraphNotReady,
    GraphTimeout,
    ImportValidationError,
    graph_status,
    import_snapshot,
    run,
)

pytestmark = pytest.mark.neo4j
URI = os.getenv("CITEHOP_TEST_NEO4J_URI")


def art(i, rev=1, title=None):
    return (i, title or f"Article {i}", f"https://en.wikipedia.org/wiki/A{i}", rev)


# 1 -> 2 -> 3 -> 1 is a cycle, 4 links to itself, 5 is isolated.
BASE = build_snapshot(
    [art(i) for i in range(1, 6)],
    [(1, "ML"), (2, "ML"), (3, "Statistics"), (4, "ML")],
    [(1, 2), (2, 3), (3, 1), (4, 4), (1, 4)],
)


@pytest.fixture
def driver():
    if not URI:
        pytest.skip("CITEHOP_TEST_NEO4J_URI not set")
    drv = GraphDatabase.driver(URI, auth=(os.getenv("CITEHOP_TEST_NEO4J_USER", "neo4j"),
                                          os.environ["CITEHOP_TEST_NEO4J_PASSWORD"]))
    run(drv, "MATCH (n) WHERE n:CiteHop OR n:CiteHopGraphMeta DETACH DELETE n", write=True)
    yield drv
    drv.close()


def namespace_counts(drv):
    q = """
    MATCH (n:CiteHop) WITH count(n) AS nodes
    OPTIONAL MATCH (:CiteHop)-[r]->(:CiteHop)
    RETURN nodes, count(r) AS edges
    """
    row = run(drv, q)[0]
    return row["nodes"], row["edges"]


def ready(drv, snapshot=BASE):
    return GraphQueries(drv, lambda: snapshot.version, timeout=5)


def test_import_twice_is_idempotent(driver):
    first = import_snapshot(driver, BASE, batch_size=2)
    counts = namespace_counts(driver)
    second = import_snapshot(driver, BASE, batch_size=3)
    assert namespace_counts(driver) == counts == (7, 9)  # 5 articles + 2 categories
    assert first.counts == second.counts
    assert (second.deleted_nodes, second.deleted_edges) == (0, 0)
    assert ready(driver).status().status == "ready"


def test_changed_and_deleted_records_reconcile_and_foreign_data_survives(driver):
    # Shared-database data: duplicate article_ids, one equal to a CiteHop ID, and a Category.
    run(driver, """
        CREATE (:Article {article_id: 'foreign'})-[:LINKS_TO]->(:Other {k: 1}),
               (:Article {article_id: 1}), (:Article {article_id: 1}), (:Category {name: 'ML'})
        """, write=True)
    import_snapshot(driver, BASE)
    changed = build_snapshot(
        [art(1, rev=2, title="Renamed"), art(2), art(3), art(5)],  # article 4 deleted
        [(1, "ML"), (2, "Statistics")],  # 3 loses Statistics -> moves to 2, 4 gone
        [(1, 2), (2, 3), (1, 4)],  # 3 -> 1 removed; 1 -> 4 orphaned and skipped
    )
    result = import_snapshot(driver, changed)
    assert result.skipped_links == 1
    assert result.deleted_nodes == 1 and result.deleted_edges >= 3
    assert namespace_counts(driver) == (6, 4)
    a1 = run(driver, "MATCH (a:CiteHop:Article {article_id: 1}) RETURN a {.*} AS a")[0]["a"]
    assert (a1["title"], a1["revision_id"]) == ("Renamed", 2)
    assert store.validate(driver, changed) == []
    foreign = run(driver, "MATCH (:Article {article_id: 'foreign'})-[r]->(:Other) RETURN count(r)")
    assert foreign[0][0] == 1
    outside = "MATCH (n) WHERE (n:Article OR n:Category) AND NOT n:CiteHop RETURN count(n)"
    assert run(driver, outside)[0][0] == 4
    run(driver, "MATCH (n) WHERE (n:Article OR n:Category OR n:Other) AND NOT n:CiteHop "
                "DETACH DELETE n", write=True)


def test_interrupted_import_is_reported_rebuilding(driver, monkeypatch):
    import_snapshot(driver, BASE)
    real = store._write_batches

    def fail_on_links(drv, cypher, *args):
        if cypher is store.UPSERT_LINKS:
            raise RuntimeError("killed mid-import")
        return real(drv, cypher, *args)

    monkeypatch.setattr(store, "_write_batches", fail_on_links)
    changed = build_snapshot([art(1), art(2)], [], [(1, 2)])
    with pytest.raises(RuntimeError):
        import_snapshot(driver, changed)
    status = ready(driver, changed).status()
    assert status.status == "rebuilding" and status.imported_version is None
    assert "killed mid-import" in status.detail
    with pytest.raises(GraphNotReady):
        ready(driver, changed).neighborhood(1)

    monkeypatch.setattr(store, "_write_batches", real)
    import_snapshot(driver, changed)
    assert ready(driver, changed).status().status == "ready"


def test_failed_validation_is_not_marked_current(driver, monkeypatch):
    monkeypatch.setattr(store, "validate", lambda *a, **k: ["links: 1 unexpected, 0 missing"])
    with pytest.raises(ImportValidationError):
        import_snapshot(driver, BASE)
    assert graph_status(driver, BASE.version).status == "rebuilding"


def test_stale_when_mariadb_changes_or_is_unreadable(driver):
    import_snapshot(driver, BASE)
    stale = GraphQueries(driver, lambda: "sha256:different").status()
    assert stale.status == "stale" and stale.imported_version == BASE.version
    with pytest.raises(GraphNotReady):
        GraphQueries(driver, lambda: "sha256:different").path(1, 2)

    def down():
        raise ConnectionError("MariaDB down")

    assert GraphQueries(driver, down).status().status == "stale"


def test_never_imported_is_unavailable(driver):
    assert graph_status(driver, BASE.version).status == "unavailable"


def test_database_errors_report_unavailable_not_raise(driver):
    status = graph_status(driver, BASE.version, database="no-such-db")
    assert status.status == "unavailable" and "no-such-db" in status.detail.lower()


def test_neighborhood_handles_cycles_and_types(driver):
    import_snapshot(driver, BASE)
    g = ready(driver)
    one = g.neighborhood(1, rel_types=("LINKS_TO",))
    assert [n["id"] for n in one["nodes"]] == ["article:1", "article:2", "article:3", "article:4"]
    assert not one["truncated"] and one["graph_version"] == BASE.version
    assert {(e["source"], e["target"]) for e in one["edges"]} == {
        ("article:1", "article:2"), ("article:2", "article:3"), ("article:3", "article:1"),
        ("article:1", "article:4"), ("article:4", "article:4")}
    two = g.neighborhood(1, hops=2)
    ids = [n["id"] for n in two["nodes"]]
    assert len(ids) == len(set(ids))
    assert {"category:ML", "category:Statistics"} <= set(ids)
    cats = g.neighborhood(3, rel_types=("IN_CATEGORY",))
    assert [n["id"] for n in cats["nodes"]] == ["article:3", "category:Statistics"]
    with pytest.raises(GraphNotFound):
        g.neighborhood(999)


def test_caps_are_deterministic_and_edges_stay_inside(driver):
    hub = build_snapshot([art(i) for i in range(0, 130)], [],
                         [(0, i) for i in range(1, 130)] + [(i, i + 1) for i in range(1, 129)])
    import_snapshot(driver, hub)
    g = ready(driver, hub)
    a = g.neighborhood(0, hops=2, max_nodes=100, max_edges=200)
    b = g.neighborhood(0, hops=2, max_nodes=100, max_edges=200)
    assert a == b and a["truncated"] and len(a["nodes"]) == 100
    ids = {n["id"] for n in a["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in a["edges"])
    small = g.neighborhood(0, max_nodes=10, max_edges=5)
    assert len(small["nodes"]) == 10 and len(small["edges"]) == 5 and small["truncated"]
    assert all("article:0" in (e["source"], e["target"]) for e in small["edges"])


def test_path_is_bounded_directed_and_deterministic(driver):
    snap = build_snapshot([art(i) for i in range(1, 8)], [(1, "ML"), (6, "ML")],
                          [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (5, 6), (6, 7)])
    import_snapshot(driver, snap)
    g = ready(driver, snap)
    p = g.path(1, 4)
    assert p["found"] and [n["id"] for n in p["nodes"]] == ["article:1", "article:2", "article:4"]
    assert g.path(1, 4) == p
    assert g.path(1, 5)["found"]
    far = g.path(1, 6)  # 4 links away; the shared ML category must not shortcut it
    assert not far["found"] and far["message"] == "No path within 3 links"
    assert not g.path(4, 1)["found"]
    back = g.path(4, 1, directed=False)
    assert back["found"] and back["edges"][0] == {
        "source": "article:2", "type": "LINKS_TO", "target": "article:4"}
    assert g.path(3, 3)["nodes"][0]["id"] == "article:3"
    with pytest.raises(GraphNotFound):
        g.path(1, 999)


def test_timeout_is_enforced(driver):
    with pytest.raises(GraphTimeout):
        run(driver, "UNWIND range(1, 1000000000) AS x RETURN sum(x)", timeout=0.5)
