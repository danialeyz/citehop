"""Load a realistic-size retrieval fixture into a DISPOSABLE database for plan inspection.

    CITEHOP_TEST_DB_NAME=citehop_test python scripts/search_fixture.py [--snapshot PATH]
    CITEHOP_TEST_DB_NAME=citehop_test python scripts/search_fixture.py --compare 50

Real C03 articles/categories/links, plus fixture chunks: fixed 1,200-character windows
(stride 1,000) with deterministic pseudo-random unit vectors. They are NOT C05 chunks or
BGE embeddings; use them only to observe query plans and exercise SQL at corpus scale.
Drops and recreates the corpus tables in CITEHOP_TEST_DB_NAME. `--compare N` skips loading
and reports ANN-vs-exact overlap@k for N seeded random query vectors (a hard case for HNSW).
"""

import argparse
import hashlib
import json
import os
import random
import statistics
import time
from pathlib import Path

from citehop.apply_sql import statements
from citehop.corpus import load
from citehop.db import configure, connect
from citehop.search import overlap_at_k, search

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("chunks", "article_links", "article_categories", "articles", "corpus_versions")
WINDOW, STRIDE = 1200, 1000
CONFIG = "fixture".ljust(64, "0")


def vector(chunk_id):
    rng = random.Random(chunk_id)
    values = [rng.gauss(0, 1) for _ in range(768)]
    norm = sum(v * v for v in values) ** 0.5
    return json.dumps([round(v / norm, 6) for v in values])


def compare(conn, n, ks=(5, 10)):
    report = {}
    for k in ks:
        overlaps, timings = [], {"vector": [], "exact": []}
        for seed in range(n):
            query = json.loads(vector(f"query-{seed}"))
            hits = {}
            for method in timings:
                start = time.perf_counter()
                hits[method] = search("fixture", method, k=k, connection=conn,
                                      query_vector=query)
                timings[method].append((time.perf_counter() - start) * 1000)
            overlaps.append(overlap_at_k(hits["vector"], hits["exact"]))
        report[f"k={k}"] = {
            "queries": n, "mean_overlap": round(statistics.mean(overlaps), 3),
            "min_overlap": min(overlaps),
            **{f"{m}_median_ms": round(statistics.median(t), 2) for m, t in timings.items()},
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/wikipedia/full.json")
    parser.add_argument("--compare", type=int, metavar="N", help="compare ANN with exact only")
    args = parser.parse_args()
    configure()
    test_db = os.getenv("CITEHOP_TEST_DB_NAME")
    if not test_db or test_db == os.getenv("DB_NAME", "citehop"):
        raise SystemExit("set CITEHOP_TEST_DB_NAME to a dedicated, disposable database")
    os.environ["DB_NAME"] = test_db
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone() == (test_db,)
        if args.compare:
            print(json.dumps(compare(conn, args.compare), indent=2))
            return
        for table in TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        for query in statements((ROOT / "sql/corpus_schema.sql").read_text()):
            cursor.execute(query)
        snapshot = json.loads(args.snapshot.read_text())
        manifest = json.loads((ROOT / "eval/corpus.json").read_text())
        load(conn, snapshot, manifest)
        rows = []
        for record in snapshot["articles"]:
            text = record["text"]
            for ordinal, start in enumerate(range(0, max(len(text) - WINDOW, 0) + 1, STRIDE)):
                end = min(start + WINDOW, len(text))
                chunk_id = hashlib.sha256(f"{record['article_id']}:{ordinal}".encode()).hexdigest()
                rows.append((chunk_id, record["article_id"], record["revision_id"], CONFIG,
                             ordinal, start, end, 1, text[start:end], vector(chunk_id), CONFIG))
        for i in range(0, len(rows), 100):  # stay under max_allowed_packet
            cursor.executemany(
                "INSERT INTO chunks (chunk_id, article_id, revision_id, chunk_config, ordinal, "
                "char_start, char_end, token_count, text, embedding, embedding_config) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, VEC_FromText(?), ?)", rows[i:i + 100])
        conn.commit()
        cursor.execute("ANALYZE TABLE chunks, articles, article_categories, article_links")
        cursor.fetchall()
    print(f"{len(snapshot['articles'])} articles, {len(rows)} fixture chunks in {test_db}")


if __name__ == "__main__":
    main()
