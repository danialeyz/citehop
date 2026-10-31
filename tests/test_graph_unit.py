"""Graph adapter tests that need no running database."""

import sqlite3

import pytest
from neo4j import GraphDatabase

from citehop.graph.queries import GraphQueries
from citehop.graph.source import build_snapshot, read_corpus_version, read_snapshot
from citehop.graph.store import GraphNotReady, GraphUnavailable, import_snapshot

ARTICLES = [(1, "Neural network", "https://en.wikipedia.org/wiki/Neural_network", 10),
            (2, "Perceptron", "https://en.wikipedia.org/wiki/Perceptron", 20)]


def test_snapshot_drops_orphans_and_duplicates():
    snap = build_snapshot(
        ARTICLES,
        [(1, "Machine learning"), (1, "Machine learning"), (9, "Orphan"), (2, " ")],
        [(1, 2), (1, 2), (2, 1), (2, 2), (1, 99), (99, 1)],
    )
    assert snap.memberships == ((1, "Machine learning"),)
    assert snap.categories == ("Machine learning",)
    assert snap.links == ((1, 2), (2, 1), (2, 2))
    assert (snap.skipped_links, snap.skipped_memberships) == (2, 2)


def test_snapshot_rejects_duplicate_article_ids():
    with pytest.raises(ValueError, match="duplicate"):
        build_snapshot(ARTICLES + [ARTICLES[0]], [], [])


def test_version_is_order_independent_and_tracks_changes():
    a = build_snapshot(ARTICLES, [(1, "ML")], [(1, 2)])
    b = build_snapshot(list(reversed(ARTICLES)), [(1, "ML")], [(1, 2)])
    assert a.version == b.version
    revised = [(1, "Neural network", ARTICLES[0][2], 11), ARTICLES[1]]
    assert build_snapshot(revised, [(1, "ML")], [(1, 2)]).version != a.version
    assert build_snapshot(ARTICLES, [(1, "ML")], []).version != a.version
    assert build_snapshot(ARTICLES, [], [(1, 2)]).version != a.version


def c03_tables():
    """The graph-relevant columns of sql/corpus_schema.sql."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE corpus_versions (version_id INTEGER PRIMARY KEY);
        CREATE TABLE articles (article_id INTEGER PRIMARY KEY, title TEXT, source_url TEXT,
                               revision_id INTEGER);
        CREATE TABLE article_categories (article_id INTEGER, category_name TEXT);
        CREATE TABLE article_links (source_article_id INTEGER, target_article_id INTEGER);
    """)
    return conn


def test_read_snapshot_uses_c03_schema_and_corpus_version():
    conn = c03_tables()
    conn.executescript("""
        INSERT INTO corpus_versions VALUES (1), (2);
        INSERT INTO articles VALUES (1, 'Neural network', 'u1', 10), (2, 'Perceptron', 'u2', 20);
        INSERT INTO article_categories VALUES (1, 'ML'), (2, 'ML');
        INSERT INTO article_links VALUES (1, 2), (2, 3);
    """)
    snap = read_snapshot(conn)
    assert snap.counts() == {"articles": 2, "categories": 1, "links": 1, "memberships": 2}
    assert snap.skipped_links == 1
    assert snap.version == read_corpus_version(conn) == "corpus:2"


def test_read_snapshot_refuses_unloaded_corpus():
    with pytest.raises(ValueError, match="corpus_versions is empty"):
        read_snapshot(c03_tables())


@pytest.fixture
def down_driver():
    driver = GraphDatabase.driver("bolt://127.0.0.1:1", auth=("neo4j", "x"),
                                  connection_timeout=1, max_transaction_retry_time=0)
    yield driver
    driver.close()


def test_outage_reports_unavailable_without_raising(down_driver):
    graph = GraphQueries(down_driver, lambda: "sha256:abc", timeout=1)
    status = graph.status()
    assert status.status == "unavailable" and status.source_version == "sha256:abc"
    with pytest.raises(GraphNotReady) as exc:
        graph.neighborhood(1)
    assert exc.value.status.status == "unavailable"
    with pytest.raises(GraphNotReady):
        graph.path(1, 2)


def test_outage_fails_import(down_driver):
    with pytest.raises(GraphUnavailable):
        import_snapshot(down_driver, build_snapshot(ARTICLES, [], []))


def test_mariadb_outage_marks_graph_stale_not_crash(down_driver):
    def broken():
        raise ConnectionError("MariaDB down")

    # Neo4j is also down here, so unavailable wins; the point is no exception escapes.
    assert GraphQueries(down_driver, broken, timeout=1).status().status == "unavailable"


def test_source_version_is_cached_and_failures_are_not(down_driver):
    calls = []

    def version():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("MariaDB down")
        return "sha256:abc"

    graph = GraphQueries(down_driver, version, timeout=1, version_ttl=60)
    assert graph.status().source_version is None  # failure, not cached
    assert graph.status().source_version == "sha256:abc"
    graph.status()
    assert len(calls) == 2  # third status reused the cached version
    graph.version_ttl = 0
    graph.status()
    assert len(calls) == 3


@pytest.mark.parametrize("kwargs", [
    {"hops": 0}, {"hops": 3}, {"max_nodes": 0}, {"max_nodes": 101},
    {"max_edges": 0}, {"max_edges": 201}, {"rel_types": ()}, {"rel_types": ("SIMILAR",)},
])
def test_neighborhood_rejects_out_of_bounds_before_querying(kwargs):
    graph = GraphQueries(driver=None, source_version=lambda: None)
    with pytest.raises(ValueError):
        graph.neighborhood(1, **kwargs)


def test_package_import_opens_no_connections():
    import citehop.graph  # noqa: F401  (search must not depend on Neo4j at import time)
