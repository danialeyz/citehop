"""Retrieval tests. Unit tests need no database; `db` tests use CITEHOP_TEST_DB_NAME."""

import math
from dataclasses import asdict
from fractions import Fraction

import pytest
from corpus_fixtures import corpus
from test_corpus_db import db, rows  # noqa: F401  (pytest fixture reuse)

from citehop import search as s

# ---------- input validation and SQL shape (no database) ----------


@pytest.mark.parametrize("query", ["", "   ", None, 42, "x" * (s.MAX_QUERY_CHARS + 1)])
def test_rejects_empty_or_oversized_query(query):
    with pytest.raises(ValueError):
        s.validate(query, "keyword", None, 5)


@pytest.mark.parametrize("k", [0, -1, s.MAX_K + 1, 2.5, "5", True])
def test_k_is_bounded_integer(k):
    with pytest.raises(ValueError):
        s.validate("q", "keyword", None, k)


@pytest.mark.parametrize("filters", [
    {"unknown": 1}, {"min_length_chars": -1}, {"max_length_chars": "10"},
    {"min_length_chars": 10, "max_length_chars": 5}, {"category": ""}, {"category": 3},
    {"linked_from": "7"}, {"linked_from": True},
])
def test_rejects_invalid_filters(filters):
    with pytest.raises(ValueError):
        s.validate("q", "vector", filters, 5)


def test_rejects_unknown_method_and_normalizes_query():
    with pytest.raises(ValueError):
        s.validate("q", "bm25", None, 5)
    assert s.validate("  q  ", "exact", None, 5) == ("q", {})


@pytest.mark.parametrize("vector", [[0.0] * 768, [1.0] * 767, [math.nan] + [1.0] * 767])
def test_rejects_bad_query_vectors(vector):
    with pytest.raises(ValueError):
        s.vector_text(vector)


def test_filters_are_sql_predicates_before_limit_and_values_are_parameters():
    filters = {"category": "x' OR '1'='1", "min_length_chars": 1, "max_length_chars": 9,
               "linked_from": 7}
    for method in s.SQL_METHODS:
        sql, params = s.build_sql(method, filters, 5)
        assert "x' OR" not in sql and sql.count("?") == len(params)
        assert sql.index("EXISTS") < sql.index("ORDER BY") < sql.index("LIMIT ?")
        assert params[-1] == 5 and filters["category"] in params
    assert "IGNORE INDEX (vx_chunks_embedding)" in s.build_sql("exact", {}, 5)[0]
    assert "IGNORE INDEX" not in s.build_sql("vector", {}, 5)[0]
    # Index + WHERE would post-filter a bounded HNSW candidate list, so filters force exact.
    assert "IGNORE INDEX" in s.build_sql("vector", {"category": "x"}, 5)[0]
    assert "IGNORE INDEX" in s.build_sql("vector", {}, 5, embedding_config="e")[0]


def test_invalid_input_never_reaches_the_embedder_or_database():
    def embedder(_):
        raise AssertionError("embedder called")

    with pytest.raises(ValueError):
        s.search("", "vector", embedder=embedder, connection=object())


def test_missing_embedder_is_reported(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "citehop.embed", None)
    with pytest.raises(s.EmbedderUnavailable):
        s.search("q", "vector", connection=object())


def test_overlap_at_k():
    hit = lambda cid: s.Hit(cid, 1, "t", "u", "p", 1, 0.5, "vector")  # noqa: E731
    assert s.overlap_at_k([hit("a"), hit("b")], [hit("a"), hit("c")]) == 0.5
    assert s.overlap_at_k([hit("a")], []) is None


# ---------- reciprocal rank fusion (S01) ----------

def ranked(method, chunk_ids):
    return [s.Hit(cid, 1, "t", "u", "p", rank, 10.0 - rank, method)
            for rank, cid in enumerate(chunk_ids, 1)]


def test_rrf_scores_are_exact_reciprocal_rank_sums():
    fused = s.rrf([ranked("keyword", ["a", "b", "c"]), ranked("vector", ["c", "a", "d"])], k=10)
    assert [h.chunk_id for h in fused] == ["a", "c", "b", "d"]
    assert [h.score for h in fused] == [float(Fraction(1, 61) + Fraction(1, 62)),
                                        float(Fraction(1, 61) + Fraction(1, 63)),
                                        float(Fraction(1, 62)), float(Fraction(1, 63))]
    assert [h.rank for h in fused] == [1, 2, 3, 4] and {h.method for h in fused} == {"hybrid"}
    assert s.RRF_K == 60 and s.RRF_DEPTH == 50


def test_rrf_overlap_is_one_hit_with_every_source():
    fused = s.rrf([ranked("keyword", ["a", "b"]), ranked("vector", ["b"])], k=10)
    assert [h.chunk_id for h in fused] == ["b", "a"]  # 1/62 + 1/61 beats 1/61
    assert fused[0].sources == (s.Source("keyword", 2, 8.0), s.Source("vector", 1, 9.0))
    assert fused[1].sources == (s.Source("keyword", 1, 9.0),)
    assert asdict(fused[0])["sources"] == ({"method": "keyword", "rank": 2, "score": 8.0},
                                           {"method": "vector", "rank": 1, "score": 9.0})


def test_rrf_ties_break_on_chunk_id_and_sums_tie_exactly():
    # Single-list rank 1 in either list ties; so do (2, 3) and (3, 2) rank pairs.
    fused = s.rrf([ranked("keyword", ["z", "p", "q"]), ranked("vector", ["y", "q", "p"])], k=10)
    assert [h.chunk_id for h in fused] == ["p", "q", "y", "z"]
    assert fused[0].score == fused[1].score and fused[2].score == fused[3].score == 1 / 61


def test_rrf_truncates_to_k_and_handles_empty_lists():
    fused = s.rrf([ranked("keyword", ["a", "b", "c"]), ranked("vector", [])], k=2)
    assert [(h.chunk_id, h.rank) for h in fused] == [("a", 1), ("b", 2)]
    assert s.rrf([[], []], k=5) == []


class FakeCursor:
    def __init__(self, log):
        self.log, self.rows = log, []

    def execute(self, sql, params=()):
        self.log.append((sql, list(params)))
        if sql.startswith("SELECT DISTINCT embedding_config"):
            self.rows = [("e",)]
        else:
            ids = ["k1", "both"] if "MATCH(" in sql else ["both", "v2"]
            self.rows = [(cid, 7, "Title", "url", "text", 0.5) for cid in ids]

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.log = []

    def cursor(self):
        return FakeCursor(self.log)


def test_hybrid_reuses_filters_at_depth_50_and_embeds_once():
    conn, calls = FakeConnection(), []
    filters = {"category": "Neural networks", "max_length_chars": 9000}
    hits = s.search("backprop", "hybrid", filters, k=2, connection=conn,
                    embedder=lambda q: calls.append(q) or AXIS, embedding_config="e")
    assert calls == ["backprop"]
    selects = [(sql, params) for sql, params in conn.log if "FROM chunks c" in sql]
    assert [s.build_sql(m, filters, 50)[0] for m in ("keyword", "vector")] == [
        sql for sql, _ in selects]
    for _, params in selects:
        assert params[-1] == s.RRF_DEPTH and "Neural networks" in params and 9000 in params
    assert [(h.chunk_id, h.rank) for h in hits] == [("both", 1), ("k1", 2)]
    assert hits[0].sources == (s.Source("keyword", 2, 0.5), s.Source("vector", 1, 0.5))


def test_hybrid_rejects_bad_input_before_sql():
    conn = FakeConnection()
    for args in (("", "hybrid"), ("q", "hybrid")):
        with pytest.raises(ValueError):
            s.search(*args, connection=conn, query_vector=[0.0] * 768)
    assert conn.log == []


# ---------- MariaDB fixtures ----------

def unit(angle):
    """768-d vector whose cosine similarity to axis 0 is cos(angle)."""
    return [math.cos(angle), math.sin(angle)] + [0.0] * 766


AXIS = unit(0.0)


def add(connection, aid, ordinal, vector, text="filler words only"):
    revision = aid * 10  # corpus_fixtures revision convention
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO chunks (chunk_id, article_id, revision_id, chunk_config, ordinal, "
        "char_start, char_end, token_count, text, embedding, embedding_config) "
        "VALUES (?, ?, ?, ?, ?, 0, 5, 2, ?, VEC_FromText(?), ?)",
        (f"c{aid}-{ordinal:03d}", aid, revision, "k" * 64, ordinal, text,
         s.vector_text(vector), "e" * 64))


@pytest.fixture
def loaded(db):  # noqa: F811
    """Article 1: 40 chunks close to AXIS. Article 2: ordered/tied chunks.
    Article 3 (only member of 'Classification algorithms'): one far chunk."""
    from citehop.corpus import load

    load(db, *corpus())
    for i in range(40):
        add(db, 1, i, unit(0.01 + i * 0.001))
    add(db, 2, 0, unit(0.6), "backpropagation trains networks by backpropagation")
    add(db, 2, 1, unit(0.7), "backpropagation mentioned once among other words")
    add(db, 2, 2, unit(0.7), "duplicate vector, later id")
    add(db, 3, 0, unit(1.4), "the perceptron is a linear classifier")
    db.commit()
    return db


def ids(hits):
    return [h.chunk_id for h in hits]


@pytest.mark.db
def test_vector_and_exact_rank_by_cosine_with_deterministic_ties(loaded):
    for method in ("vector", "exact"):
        hits = s.search("q", method, {"category": "Neural networks", "max_length_chars": 35},
                        k=3, connection=loaded, query_vector=AXIS)
        # 'Neural networks' holds articles 2 (35 chars) and 3 (38 chars); the length cuts 3.
        assert ids(hits) == ["c2-000", "c2-001", "c2-002"]
        assert [h.rank for h in hits] == [1, 2, 3] and {h.method for h in hits} == {method}
        assert hits[0].score == pytest.approx(math.cos(0.6), abs=1e-5)
        assert hits[0].title == "Deep learning" and hits[0].source_url.endswith("Deep_learning")


@pytest.mark.db
def test_eligible_hit_outside_global_top_k_is_found(loaded):
    unfiltered = s.search("q", "exact", None, k=30, connection=loaded, query_vector=AXIS)
    assert "c3-000" not in ids(unfiltered)  # 40 article-1 chunks are closer
    for method in ("vector", "exact"):
        for filters in ({"category": "Classification algorithms"}, {"linked_from": 2,
                                                                      "min_length_chars": 38}):
            hits = s.search("q", method, filters, k=5, connection=loaded, query_vector=AXIS)
            assert ids(hits) == ["c3-000"], (method, filters)


@pytest.mark.db
def test_ann_matches_exact_on_unfiltered_fixture(loaded):
    ann = s.search("q", "vector", None, k=10, connection=loaded, query_vector=AXIS)
    exact = s.search("q", "exact", None, k=10, connection=loaded, query_vector=AXIS)
    assert ids(exact) == [f"c1-{i:03d}" for i in range(10)]
    assert s.overlap_at_k(ann, exact) == 1.0


@pytest.mark.db
def test_keyword_uses_fulltext_relevance_and_filters(loaded):
    hits = s.search("backpropagation", "keyword", None, k=5, connection=loaded)
    assert ids(hits) == ["c2-000", "c2-001"] and hits[0].score > hits[1].score > 0
    assert s.search("backpropagation", "keyword", {"category": "Classification algorithms"},
                    k=5, connection=loaded) == []
    assert s.search("an of", "keyword", None, k=5, connection=loaded) == []  # too short


@pytest.mark.db
def test_no_duplicate_chunks_from_category_and_link_joins(loaded):
    # Articles have several categories and links; each chunk appears at most once.
    for filters in (None, {"category": "Machine learning"}, {"linked_from": 2}):
        hits = s.search("q", "exact", filters, k=s.MAX_K, connection=loaded, query_vector=AXIS)
        assert len(ids(hits)) == len(set(ids(hits)))
    assert len(s.search("q", "exact", None, k=s.MAX_K, connection=loaded,
                        query_vector=AXIS)) == 44


@pytest.mark.db
def test_hostile_strings_are_data(loaded):
    evil = "x'); DROP TABLE chunks; -- \\ \" %"
    assert s.search(evil, "keyword", {"category": evil}, connection=loaded) == []
    assert s.search("q", "vector", {"category": evil}, connection=loaded,
                    query_vector=AXIS) == []
    assert rows(loaded, "SELECT COUNT(*) FROM chunks") == [(44,)]


@pytest.mark.db
def test_embedding_config_restricts_rows(loaded):
    # E.g. a CPU query embedder against a corpus embedded with --device mps.
    for method in ("keyword", "vector", "exact"):
        with pytest.raises(ValueError, match="no chunks have embedding_config"):
            s.search("perceptron", method, None, connection=loaded, query_vector=AXIS,
                     embedding_config="other")
    assert len(s.search("q", "exact", None, connection=loaded, query_vector=AXIS,
                        embedding_config="e" * 64)) == 5


@pytest.mark.db
def test_mixed_embedding_configs_need_an_explicit_choice(loaded):
    cursor = loaded.cursor()
    cursor.execute("UPDATE chunks SET embedding_config = ? WHERE chunk_id = 'c3-000'",
                   ("f" * 64,))
    loaded.commit()
    with pytest.raises(ValueError, match="several embedding configurations"):
        s.search("perceptron", "keyword", connection=loaded)
    hits = s.search("q", "vector", {"category": "Classification algorithms"},
                    connection=loaded, query_vector=AXIS, embedding_config="f" * 64)
    assert ids(hits) == ["c3-000"]
    assert s.search("q", "vector", {"category": "Classification algorithms"},
                    connection=loaded, query_vector=AXIS, embedding_config="e" * 64) == []


@pytest.mark.db
def test_plans_use_vector_index_only_for_ann(loaded):
    value = s.vector_text(AXIS)
    keys = lambda plan: {row["key"] for row in plan}  # noqa: E731
    assert "vx_chunks_embedding" in keys(s.explain("vector", {}, 5, value, loaded))
    assert "vx_chunks_embedding" in keys(s.explain("vector", {}, 5, value, loaded,
                                                   embedding_config="e" * 64))
    for method, filters in (("exact", {}), ("vector", {"category": "Neural networks"})):
        assert "vx_chunks_embedding" not in keys(s.explain(method, filters, 5, value, loaded))
    keyword = s.explain("keyword", {"category": "Neural networks"}, 5, "perceptron", loaded)
    assert "fulltext" in {row["type"] for row in keyword}


@pytest.mark.db
def test_search_never_touches_neo4j(loaded, monkeypatch):
    import citehop.db

    def refuse():
        raise AssertionError("retrieval opened Neo4j")

    monkeypatch.setattr(citehop.db, "graph_driver", refuse)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    assert s.search("perceptron", "keyword", connection=loaded)
    assert s.search("q", "vector", connection=loaded, query_vector=AXIS)


@pytest.mark.db
def test_hybrid_fuses_filtered_keyword_and_vector_lists(loaded):
    filters = {"category": "Neural networks"}
    hits = s.search("backpropagation", "hybrid", filters, k=10, connection=loaded,
                    query_vector=AXIS)
    # keyword: c2-000, c2-001; vector over articles 2 and 3: c2-000, c2-001, c2-002, c3-000.
    assert [(h.chunk_id, h.score) for h in hits] == [
        ("c2-000", 2 / 61), ("c2-001", 2 / 62), ("c2-002", 1 / 63), ("c3-000", 1 / 64)]
    assert [src.method for src in hits[0].sources] == ["keyword", "vector"]
    assert hits[3].sources[0].method == "vector" and hits[3].title == "Perceptron"
    inputs = [s.search("backpropagation", m, filters, k=s.RRF_DEPTH, connection=loaded,
                       query_vector=AXIS) for m in s.RRF_INPUTS]
    assert hits == s.rrf(inputs, 10)
    assert s.search("backpropagation", "hybrid", {"category": "Classification algorithms"},
                    k=5, connection=loaded, query_vector=AXIS)[0].chunk_id == "c3-000"
