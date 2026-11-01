"""Schema tests from CITEHOP_BOOTSTRAP.md 4.20, adapted to this repo.

They apply sql/schema.sql and sql/kg_schema.sql twice to the database named by
CITEHOP_TEST_DB_NAME (never the configured DB_NAME), then inspect it. Nothing is dropped.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.db
pytest.importorskip("mariadb")
SQL = Path(__file__).resolve().parents[1] / "sql"
CORE = {"papers", "citations", "emb_bge_base", "queries", "qrels", "runs"}
KG = {"authors", "paper_authors", "venues", "concepts", "concept_aliases", "paper_concepts"}
OPS = {"search_log"}


@pytest.fixture(scope="module")
def conn():
    from citehop.apply_sql import statements
    from citehop.db import configure, connect

    configure()  # load .env first so the comparison sees the real DB_NAME
    test_db = os.getenv("CITEHOP_TEST_DB_NAME")
    if not test_db or test_db == os.getenv("DB_NAME", "citehop"):
        pytest.skip("set CITEHOP_TEST_DB_NAME to a dedicated, disposable database")
    with connect(database=test_db) as connection:
        cursor = connection.cursor()
        for _ in range(2):  # both files must be safe to rerun
            for name in ("schema.sql", "kg_schema.sql"):
                for query in statements((SQL / name).read_text(encoding="utf-8")):
                    cursor.execute(query)
        connection.commit()
        yield connection


def test_all_tables_exist(conn):
    cur = conn.cursor()
    cur.execute("SHOW FULL TABLES")
    rows = {name: kind for name, kind in cur.fetchall()}
    assert CORE <= rows.keys()
    assert KG <= rows.keys()
    assert OPS <= rows.keys()
    assert rows.get("kg_links") == "VIEW"


def test_vector_column_is_768(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'emb_bge_base' AND COLUMN_NAME = 'emb'"
    )
    (col_type,) = cur.fetchone()
    assert col_type.lower() == "vector(768)"


@pytest.mark.parametrize("table", ["emb_bge_base", "concepts"])
def test_no_vector_index_before_loading(conn, table):
    cur = conn.cursor()
    cur.execute("SHOW CREATE TABLE " + table)
    ddl = cur.fetchone()[1].upper()
    assert "VECTOR KEY" not in ddl and "VECTOR INDEX" not in ddl


def test_venue_foreign_key_added_once(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'papers'"
    )
    assert cur.fetchone() == (1,)


def test_search_log_stores_hash_not_query(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'search_log'"
    )
    columns = dict(cur.fetchall())
    assert columns["query_hash"] == "binary(32)"
    assert not {"query", "text", "query_text"} & columns.keys()
