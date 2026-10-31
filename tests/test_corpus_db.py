"""MariaDB integration tests. They DROP the corpus tables, so they only run against a
dedicated database named by CITEHOP_TEST_DB_NAME (never the configured DB_NAME)."""

import os
from pathlib import Path

import pytest
from corpus_fixtures import article, corpus, revise, snapshot_of

pytestmark = pytest.mark.db
errors = pytest.importorskip("mariadb")
SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "corpus_schema.sql"
TABLES = ("chunks", "article_links", "article_categories", "articles", "corpus_versions",
          "embedding_configs")


@pytest.fixture
def db(monkeypatch):
    from citehop.apply_sql import statements
    from citehop.db import configure, connect

    configure()  # load .env first so the comparison sees the real DB_NAME
    test_db = os.getenv("CITEHOP_TEST_DB_NAME")
    if not test_db or test_db == os.getenv("DB_NAME", "citehop"):
        pytest.skip("set CITEHOP_TEST_DB_NAME to a dedicated, disposable database")
    monkeypatch.setenv("DB_NAME", test_db)
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone() == (test_db,), "refusing to drop tables outside the test DB"
        for table in TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        for _ in range(2):  # schema must be safe to rerun
            for query in statements(SCHEMA.read_text()):
                cursor.execute(query)
        connection.commit()
        yield connection


def add_chunk(connection, aid, revision, ordinal=0):
    vector = "[" + ",".join(["0.1"] * 767 + [str(0.2 + ordinal)]) + "]"
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO chunks (chunk_id, article_id, revision_id, chunk_config, ordinal, "
        "char_start, char_end, token_count, text, embedding, embedding_config) "
        "VALUES (?, ?, ?, ?, ?, 0, 5, 2, 'hello', VEC_FromText(?), ?)",
        (f"{aid:032d}{revision:016d}{ordinal:016d}", aid, revision, "k" * 64, ordinal,
         vector, "e" * 64))
    connection.commit()


def rows(connection, query):
    cursor = connection.cursor()
    cursor.execute(query)
    return cursor.fetchall()


def test_rerun_preserves_counts_and_version(db):
    from citehop.corpus import counts, load

    snapshot, manifest = corpus()
    first = load(db, snapshot, manifest, batch_size=2)
    assert first["version_advanced"] and first["articles_written"] == 3
    before = counts(db)
    assert before == {"articles": 3, "article_categories": 6, "article_links": 5, "chunks": 0,
                      "distinct_categories": 4, "corpus_version": first["corpus_version"]}
    again = load(db, snapshot, manifest, batch_size=2)
    assert not again["version_advanced"] and again["articles_written"] == 0
    assert again["links_added"] == again["categories_added"] == 0
    assert counts(db) == before


def test_changed_revision_invalidates_chunks_and_advances_version(db):
    from citehop.corpus import load

    snapshot, manifest = corpus()
    first = load(db, snapshot, manifest)
    add_chunk(db, 2, 20)
    add_chunk(db, 3, 30)
    revised = revise(snapshot, manifest, 3, "The perceptron was revised.")
    report = load(db, *revised)
    assert report["revisions_changed"] == 1 and report["chunks_invalidated"] == 1
    assert report["corpus_version"] == first["corpus_version"] + 1
    assert rows(db, "SELECT article_id, revision_id FROM chunks") == [(2, 20)]
    assert rows(db, "SELECT revision_id FROM articles WHERE article_id = 3") == [(31,)]


def test_stale_chunk_blocks_direct_revision_update(db):
    from citehop.corpus import load

    load(db, *corpus())
    add_chunk(db, 1, 10)
    cursor = db.cursor()
    with pytest.raises(errors.IntegrityError):
        cursor.execute("UPDATE articles SET revision_id = 11 WHERE article_id = 1")
    db.rollback()
    with pytest.raises(errors.IntegrityError):  # chunk for a revision that is not current
        add_chunk(db, 1, 9)
    db.rollback()


def test_removed_articles_and_edges_reconcile(db):
    from citehop.corpus import counts, load

    snapshot, manifest = corpus()
    load(db, snapshot, manifest)
    add_chunk(db, 3, 30)
    smoke = {"corpus_id": snapshot["corpus_id"], "articles": snapshot["articles"][:2]}
    report = load(db, smoke, manifest)
    assert report["subset"] == "smoke" and report["articles_removed"] == 1
    assert report["chunks_invalidated"] == 1 and report["version_advanced"]
    assert rows(db, "SELECT * FROM article_links ORDER BY 1") == [(1, 2), (2, 1)]
    live = counts(db)
    assert (live["articles"], live["chunks"], live["article_categories"]) == (2, 0, 4)


def test_constraints_reject_orphans_duplicates_and_self_links(db):
    from citehop.corpus import load

    load(db, *corpus())
    cursor = db.cursor()
    bad = [
        "INSERT INTO article_links VALUES (1, 999)",  # orphan target
        "INSERT INTO article_links VALUES (999, 1)",  # orphan source
        "INSERT INTO article_links VALUES (1, 2)",  # duplicate edge
        "INSERT INTO article_links VALUES (1, 1)",  # self loop
        "INSERT INTO article_categories VALUES (1, 'Machine learning')",  # duplicate
        "INSERT INTO article_categories VALUES (999, 'X')",  # orphan article
        "INSERT INTO article_categories VALUES (1, '')",  # empty name
    ]
    for query in bad:
        with pytest.raises(errors.Error):
            cursor.execute(query)
        db.rollback()
    # Binary collation: accent/case variants are distinct categories, not duplicates.
    cursor.execute("INSERT INTO article_categories VALUES (1, 'Machine Learning'), "
                   "(1, 'Machine léarning')")
    db.rollback()


def test_failed_load_rolls_back(db):
    from citehop.corpus import counts, load

    snapshot, manifest = corpus()
    load(db, snapshot, manifest)
    before = counts(db)
    broken = revise(snapshot, manifest, 2, "Deep learning, revised.")
    broken[0]["articles"][1]["provenance"]["attribution"] = "x" * 600  # exceeds column
    with pytest.raises(errors.Error):
        load(db, *broken)
    assert counts(db) == before


def test_vector_and_fulltext_indexes_are_used(db):
    from citehop.corpus import load

    load(db, *corpus())
    for ordinal in range(3):
        add_chunk(db, 1, 10, ordinal)
    indexes = {(r[2], r[10]) for r in rows(db, "SHOW INDEX FROM chunks")}
    assert ("vx_chunks_embedding", "VECTOR") in indexes
    assert ("ft_chunks_text", "FULLTEXT") in indexes
    query = ("FROM chunks ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText('["
             + ",".join(["0.1"] * 768) + "]')) LIMIT 2")
    plan = rows(db, "EXPLAIN SELECT chunk_id " + query)
    assert plan[0][5] == "vx_chunks_embedding"  # EXPLAIN `key` column
    assert len(rows(db, "SELECT chunk_id " + query)) == 2
    assert rows(db, "SELECT COUNT(*) FROM chunks WHERE MATCH(text) AGAINST('hello')") == [(3,)]


def titles(connection):
    return rows(connection, "SELECT article_id, title FROM articles ORDER BY article_id")


def test_title_moving_to_new_page_id_does_not_overwrite_old_row(db):
    from citehop.corpus import load

    load(db, *snapshot_of([article(5, "Alpha", "Alpha text.", ["X"], ["Beta"]),
                           article(6, "Beta", "Beta text.", ["Y"], ["Alpha"])]))
    # Page 5 is renamed; a new page 4 (no categories or links) takes its old title.
    report = load(db, *snapshot_of([article(4, "Alpha", "New alpha page."),
                                    article(5, "Gamma", "Alpha text.", ["X"], ["Beta"]),
                                    article(6, "Beta", "Beta text.", ["Y"], ["Gamma"])]))
    assert report["articles_renamed"] == 1 and report["version_advanced"]
    assert titles(db) == [(4, "Alpha"), (5, "Gamma"), (6, "Beta")]
    assert rows(db, "SELECT text FROM articles WHERE article_id = 4") == [("New alpha page.",)]
    assert rows(db, "SELECT * FROM article_links ORDER BY 1") == [(5, 6), (6, 5)]


def test_title_rotation_across_existing_ids(db):
    from citehop.corpus import load

    load(db, *snapshot_of([article(1, "A", "one"), article(2, "B", "two"),
                           article(3, "C", "three")]))
    load(db, *snapshot_of([article(1, "B", "one"), article(2, "C", "two"),
                           article(3, "A", "three")]))
    assert titles(db) == [(1, "B"), (2, "C"), (3, "A")]
