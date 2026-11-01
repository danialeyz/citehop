"""S02 graph-assisted retrieval. Unit tests need no services; `db` tests use
CITEHOP_TEST_DB_NAME and `neo4j` tests a disposable CITEHOP_TEST_NEO4J_URI."""

import pytest
from neo4j import GraphDatabase
from test_corpus_db import db  # noqa: F401
from test_graph_neo4j import art, driver  # noqa: F401  (pytest fixture reuse)
from test_search import AXIS, loaded, unit  # noqa: F401

from citehop import graph_retrieval as g
from citehop.graph.queries import GraphQueries
from citehop.graph.source import build_snapshot
from citehop.graph.store import GraphStatus, GraphTimeout, import_snapshot
from citehop.search import Hit, eligible_sql


def hit(article_id, rank, chunk=None):
    return Hit(chunk or f"c{article_id}-{rank}", article_id, f"A{article_id}", "u", "p", rank,
               1.0 - rank / 100, "vector")


class FakeGraph:
    """GraphQueries stand-in: a fixed status and rows keyed by statement."""

    def __init__(self, status="ready", rows=None, version="corpus:1", error=None):
        self.driver, self.timeout, self.database = object(), 5, None
        self._status = GraphStatus(status, version, version, None, None,
                                   None if status == "ready" else "detail")
        self.rows, self.error, self.calls = rows or {}, error, []

    def status(self):
        return self._status

    def run(self, _driver, cypher, params, **_):
        self.calls.append((cypher, params))
        if self.error:
            raise self.error
        return self.rows.get("present" if cypher is g.SEEDS_PRESENT else "expand", [])


@pytest.fixture
def fake(monkeypatch):
    def make(**kwargs):
        graph = FakeGraph(**kwargs)
        monkeypatch.setattr("citehop.graph.store.run", graph.run)
        return graph
    return make


def row(article_id, support, first_seed=0, is_seed=False):
    return {"article_id": article_id, "support": support, "first_seed": first_seed,
            "is_seed": is_seed}


# ---------- seeds, expansion and SQL shape (no services) ----------


def test_seeds_are_distinct_articles_in_rank_order_capped_at_ten():
    hits = [hit(7, 1), hit(7, 2), hit(3, 3)] + [hit(100 + i, 4 + i) for i in range(20)]
    seeds = g.seed_articles(list(reversed(hits)))
    assert seeds == [7, 3, *range(100, 108)] and len(seeds) == g.MAX_SEEDS
    assert g.seed_articles([]) == []


@pytest.mark.parametrize("seeds,neighbors", [
    ([], 100), (list(range(11)), 100), ([1, 1], 100), ([1], 101), ([1], -1), ([1], 2.0)])
def test_expand_rejects_out_of_bounds_before_querying(fake, seeds, neighbors):
    graph = fake()
    with pytest.raises(ValueError):
        g.expand(graph, seeds, neighbors)
    assert graph.calls == []


@pytest.mark.parametrize("status", ["stale", "rebuilding", "unavailable"])
def test_graph_that_is_not_ready_is_not_queried(fake, status):
    graph = fake(status=status)
    expansion = g.expand(graph, [1, 2])
    assert not expansion.used and expansion.status == status
    assert status in expansion.fallback_reason and graph.calls == []
    assert expansion.neighbors == () and expansion.seeds == (1, 2)


def test_graph_query_failure_falls_back_instead_of_raising(fake):
    expansion = g.expand(fake(error=GraphTimeout("graph query exceeded 5s")), [1])
    assert not expansion.used and "GraphTimeout" in expansion.fallback_reason
    assert g.expand(None, [1]).fallback_reason == "no graph configured"


def test_expand_caps_neighbors_and_reports_truncation(fake):
    rows = [row(1, 1, is_seed=True)] + [row(1000 + i, 1) for i in range(g.MAX_NEIGHBORS + 1)]
    graph = fake(rows={"present": [{"article_id": 1}], "expand": rows})
    expansion = g.expand(graph, [1, 2])
    assert expansion.used and expansion.truncated and expansion.graph_version == "corpus:1"
    assert expansion.neighbors == tuple(range(1000, 1000 + g.MAX_NEIGHBORS))
    assert expansion.seeds_missing == (2,)
    assert expansion.support[1] == 1 and 1000 + g.MAX_NEIGHBORS not in expansion.support
    # The LIMIT budget covers every seed row plus one extra neighbor to detect truncation.
    assert graph.calls[-1][1]["limit"] == 2 + g.MAX_NEIGHBORS + 1
    assert graph.calls[-1][1]["seeds"] == ["article:1", "article:2"]
    small = g.expand(fake(rows={"expand": rows[:4]}), [1], max_neighbors=3)
    assert small.neighbors == (1000, 1001, 1002) and not small.truncated


def test_bonus_is_proportional_to_seed_support():
    expansion = g.Expansion("ready", "corpus:1", True, seeds=(1, 2, 3, 4),
                            neighbors=(9, 8), support={1: 2, 9: 4, 8: 0})
    assert g.bonuses(expansion) == {1: g.GRAPH_WEIGHT / 2, 9: g.GRAPH_WEIGHT}


def test_candidate_sql_keeps_filters_candidates_and_limit_in_one_statement():
    filters = {"category": "x' OR '1'='1", "min_length_chars": 1, "linked_from": 7}
    sql, params = g.build_sql(filters, [5, 3, 5], {3: 0.01, 99: 0.02}, 4, "e")
    assert "x' OR" not in sql and sql.count("?") == len(params)
    assert sql.index("IN (?, ?)") < sql.index("EXISTS") < sql.index("ORDER BY") < sql.index(
        "LIMIT ?")
    assert "IGNORE INDEX (vx_chunks_embedding)" in sql
    assert params[0] is g.QUERY and params[1:3] == [3, 0.01]  # 99 is not a candidate
    assert params[3:5] == [3, 5] and params[-1] == 4
    assert params[5:-1] == eligible_sql(filters, "e")[1]
    assert "ELSE 0" not in g.build_sql({}, [1], {}, 5)[0]
    with pytest.raises(ValueError):
        g.build_sql({}, [], {}, 5)


def test_graph_search_falls_back_to_core_vector_hits_without_a_ready_graph(fake, monkeypatch):
    seed_hits = [hit(1, 1), hit(1, 2), hit(2, 3)]
    calls = []

    def fake_search(query, method, filters, k, **kwargs):
        calls.append((method, filters, k))
        return seed_hits

    monkeypatch.setattr(g, "search", fake_search)
    for graph in (fake(status="stale"), None):
        result = g.graph_search("q", {"category": "ML"}, 2, graph=graph, connection=object(),
                                query_vector=AXIS)
        assert [h.chunk_id for h in result.hits] == ["c1-1", "c1-2"]
        assert {h.method for h in result.hits} == {"vector"} and not result.expansion.used
        assert "graph_ms" in result.timings_ms and "candidate_ms" not in result.timings_ms
    assert calls[0] == ("vector", {"category": "ML"}, g.SEED_CHUNKS)
    monkeypatch.setattr(g, "search", lambda *a, **k: [])
    empty = g.graph_search("q", None, 5, graph=fake(), connection=object(), query_vector=AXIS)
    assert empty.hits == [] and empty.expansion.status == "not_queried"


def test_real_neo4j_outage_falls_back(monkeypatch):
    monkeypatch.setattr(g, "search", lambda *a, **k: [hit(1, 1)])
    down = GraphDatabase.driver("bolt://127.0.0.1:1", auth=("neo4j", "x"),
                                connection_timeout=1, max_transaction_retry_time=0)
    try:
        result = g.graph_search("q", None, 5, graph=GraphQueries(down, lambda: "corpus:1",
                                                                 timeout=1),
                                connection=object(), query_vector=AXIS)
    finally:
        down.close()
    assert result.expansion.status == "unavailable" and [h.article_id for h in result.hits] == [1]


@pytest.mark.parametrize("kwargs", [{"max_seeds": 0}, {"max_seeds": 11}, {"k": 0}])
def test_graph_search_validates_before_embedding(kwargs):
    def embedder(_):
        raise AssertionError("embedded invalid input")

    with pytest.raises(ValueError):
        g.graph_search("q", **{"k": 5, **kwargs}, graph=None, embedder=embedder)


def test_compare_and_summary_count_recall_fallbacks_and_neighbors():
    questions = [
        {"id": "d1", "split": "dev", "question": "q1", "answerable": True, "filters": {},
         "relevant_article_ids": [2]},
        {"id": "d2", "split": "dev", "question": "q2", "answerable": True,
         "filters": {"category": "ML"}, "relevant_article_ids": [1]},
        {"id": "d3", "split": "dev", "question": "q3", "answerable": False, "filters": {},
         "relevant_article_ids": []},
    ]

    def hits(*articles):
        return [{"chunk_id": f"c{a}", "article_id": a, "rank": i, "score": 1.0}
                for i, a in enumerate(articles, 1)]

    def run_vector(question, filters, depth, vector):
        return hits(1, 3)

    def run_graph(question, filters, depth, vector):
        used = question != "q2"
        return hits(2, 1) if used else hits(1, 3), {
            "status": "ready" if used else "stale", "graph_version": "corpus:1", "used": used,
            "seeds": [1, 3], "neighbors": [2] if used else [], "truncated": False,
            "seeds_missing": [], "stage_ms": {"seed_ms": 1.0, "graph_ms": 2.0}}

    records = g.compare(questions, run_vector=run_vector, run_graph=run_graph,
                        embed_fn=lambda q: AXIS, splits=("dev",))
    summary = g.summarize(records)
    dev = summary["retrieval"]["dev"]
    assert dev["vector"]["all_answerable"]["recall_at_5"] == 0.5
    assert dev["graph"]["all_answerable"]["recall_at_5"] == 1.0
    assert dev["per_question"] == {"graph_higher": 1, "graph_lower": 0, "equal": 1}
    graph = summary["graph"]["dev"]
    assert graph["expanded"] == 2 and graph["fallbacks"] == {"stale": 1}
    assert graph["graph_versions"] == ["corpus:1"] and graph["neighbor_articles_in_top_5"] == 2
    assert summary["latency"]["dev"]["retrieval_ms_graph"]["n"] == 3
    assert graph["stage_graph_ms"]["median"] == 2.0 and graph["stage_candidate_ms"]["n"] == 0


# ---------- MariaDB: filters, ranking and deduplication on real SQL ----------


def fixed_expansion(monkeypatch, seeds, neighbors, support):
    expansion = g.Expansion("ready", "corpus:test", True, seeds=tuple(seeds),
                            neighbors=tuple(neighbors), support=support)
    monkeypatch.setattr(g, "expand", lambda graph, s, n=g.MAX_NEIGHBORS: expansion)
    return expansion


@pytest.mark.db
def test_neighbor_chunks_are_ranked_with_bonus_and_deduplicated(loaded, monkeypatch):  # noqa: F811
    # Seed search finds articles 1, 2 and 3; pretend the graph says 3 is linked to every seed.
    fixed_expansion(monkeypatch, [1, 2], [3], {3: 2, 1: 1})
    result = g.graph_search("q", None, g.MAX_K, graph=object(), connection=loaded,
                            query_vector=AXIS)
    chunk_ids = [h.chunk_id for h in result.hits]
    assert len(chunk_ids) == len(set(chunk_ids)) == 44  # categories/links cannot duplicate
    assert {h.method for h in result.hits} == {"graph"}
    assert [h.rank for h in result.hits] == list(range(1, 45))
    top = result.hits[0]
    assert top.chunk_id == "c1-000"
    assert top.score == pytest.approx(unit(0.01)[0] + g.GRAPH_WEIGHT / 2, abs=1e-5)
    perceptron = next(h for h in result.hits if h.article_id == 3)
    assert perceptron.score == pytest.approx(unit(1.4)[0] + g.GRAPH_WEIGHT, abs=1e-5)
    assert result.provenance[3] == {"role": "neighbor", "support": 2, "bonus": g.GRAPH_WEIGHT}
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.db
def test_original_filters_drop_ineligible_neighbors(loaded, monkeypatch):  # noqa: F811
    # Category 'Neural networks' holds articles 2 and 3; article 1 is a graph neighbor that
    # fails the filter and must not appear even with the largest bonus.
    fixed_expansion(monkeypatch, [2], [1, 3], {1: 1, 3: 1})
    for filters in ({"category": "Neural networks"}, {"linked_from": 1, "max_length_chars": 35}):
        result = g.graph_search("q", filters, 10, graph=object(), connection=loaded,
                                query_vector=AXIS)
        assert result.hits and 1 not in {h.article_id for h in result.hits}, filters
    eligible = g.graph_search("q", {"category": "Classification algorithms"}, 5, graph=object(),
                              connection=loaded, query_vector=AXIS)
    assert [h.chunk_id for h in eligible.hits] == ["c3-000"]


@pytest.mark.db
def test_graph_only_narrows_candidates(loaded, monkeypatch):  # noqa: F811
    fixed_expansion(monkeypatch, [2], [], {})
    result = g.graph_search("q", None, 10, graph=object(), connection=loaded, query_vector=AXIS)
    assert [h.chunk_id for h in result.hits] == ["c2-000", "c2-001", "c2-002"]


# ---------- Neo4j: one hop, cycles, caps and stale graphs on a real graph ----------

# 1 -> 2 -> 3 -> 1 is a cycle, 2 -> 1 is reciprocal, 4 links to itself, 5 has no links.
# 10 links to 100..249 (150 articles); 11 links to 200..209 as well.
STAR = range(100, 250)
SNAPSHOT = build_snapshot(
    [art(i) for i in (1, 2, 3, 4, 5, 6, 10, 11, *STAR)],
    [(1, "ML"), (2, "ML"), (3, "ML"), (5, "ML")],  # shared categories create no neighbors
    [(1, 2), (2, 3), (3, 1), (2, 1), (4, 4), (1, 4), (6, 1)]
    + [(10, t) for t in STAR] + [(11, t) for t in range(200, 210)],
)


@pytest.fixture
def imported(driver):  # noqa: F811
    import_snapshot(driver, SNAPSHOT, batch_size=100)
    return GraphQueries(driver, lambda: SNAPSHOT.version, timeout=5)


@pytest.mark.neo4j
def test_one_hop_through_cycles_and_reciprocal_links_counts_each_article_once(imported):
    expansion = g.expand(imported, [1, 3])
    assert expansion.used and expansion.graph_version == SNAPSHOT.version
    assert expansion.neighbors == (2, 4, 6)  # 2 touches both seeds; then by first seed, id
    assert expansion.support == {1: 1, 3: 1, 2: 2, 4: 1, 6: 1}
    assert not expansion.truncated and expansion.seeds_missing == ()
    self_loop = g.expand(imported, [4])
    assert self_loop.neighbors == (1,) and self_loop.support == {1: 1}
    isolated = g.expand(imported, [5, 999])
    assert isolated.used and isolated.neighbors == () and isolated.seeds_missing == (999,)


@pytest.mark.neo4j
def test_neighbor_cap_is_deterministic_and_truncation_is_reported(imported):
    first = g.expand(imported, [10, 11])
    assert first.truncated and len(first.neighbors) == g.MAX_NEIGHBORS
    assert first.neighbors[:10] == tuple(range(200, 210))  # support 2 first
    assert first.neighbors[10:] == tuple(range(100, 190))
    assert g.expand(imported, [11, 10]).neighbors[:10] == first.neighbors[:10]
    assert g.expand(imported, [10, 11]) == first
    assert not g.expand(imported, [11]).truncated


@pytest.mark.neo4j
def test_stale_graph_is_not_used(driver):  # noqa: F811
    import_snapshot(driver, SNAPSHOT, batch_size=100)
    stale = GraphQueries(driver, lambda: "corpus:other", timeout=5)
    expansion = g.expand(stale, [1])
    assert expansion.status == "stale" and not expansion.used and expansion.neighbors == ()
