"""Native MariaDB retrieval: FULLTEXT keyword search, ANN vector search, exact cosine baseline.

    python -m citehop.search "QUERY" [--method keyword|vector|exact] [--k N]
                             [--category NAME] [--min-length N] [--max-length N]
                             [--linked-from ARTICLE_ID] [--explain]

All filters are SQL predicates evaluated before the final LIMIT; Python never filters a
global top-k. Scores are method-specific (FULLTEXT relevance, or cosine similarity
1 - VEC_DISTANCE_COSINE) and are not comparable across methods or probabilities.
Keyword relevance is MariaDB InnoDB FULLTEXT natural-language relevance, not BM25.
`vector` reads the HNSW index only when unfiltered; with filters it ranks every eligible row
exactly (see build_sql). `exact` never uses the index and is the baseline for ANN recall.
Retrieval uses MariaDB only; it never opens a Neo4j connection.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from contextlib import nullcontext
from dataclasses import asdict, dataclass

METHODS = ("keyword", "vector", "exact")
MAX_K = 100
MAX_QUERY_CHARS = 1000
DIMENSIONS = 768
FILTER_KEYS = {"category", "min_length_chars", "max_length_chars", "linked_from"}


class EmbedderUnavailable(RuntimeError):
    """No query embedder is installed (C05 provides it)."""


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    article_id: int
    title: str
    source_url: str
    passage: str
    rank: int
    score: float
    method: str


def validate(query, method, filters, k):
    """Normalized (query, filters) or ValueError. Shared with the API layer."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query exceeds {MAX_QUERY_CHARS} characters")
    if method not in METHODS:
        raise ValueError(f"method must be one of {', '.join(METHODS)}")
    if type(k) is not int or not 1 <= k <= MAX_K:
        raise ValueError(f"k must be an integer from 1 to {MAX_K}")
    filters = dict(filters or {})
    if set(filters) - FILTER_KEYS:
        raise ValueError(f"unknown filter: {', '.join(sorted(set(filters) - FILTER_KEYS))}")
    for key in ("min_length_chars", "max_length_chars", "linked_from"):
        if key in filters and (type(filters[key]) is not int or filters[key] < 0):
            raise ValueError(f"{key} must be a nonnegative integer")
    if filters.get("min_length_chars", 0) > filters.get("max_length_chars", math.inf):
        raise ValueError("min_length_chars exceeds max_length_chars")
    if "category" in filters and (not isinstance(filters["category"], str)
                                  or not filters["category"]):
        raise ValueError("category must be a non-empty string")
    return query.strip(), filters


def eligible_sql(filters, embedding_config=None):
    """WHERE clauses and parameters over chunk alias `c` only.

    Article predicates are EXISTS subqueries, so category/link joins cannot duplicate a chunk.
    """
    clauses, params = [], []
    if embedding_config is not None:
        clauses.append("c.embedding_config = ?")
        params.append(embedding_config)
    lengths = [(op, filters[key]) for key, op in (("min_length_chars", ">="),
                                                  ("max_length_chars", "<="))
               if key in filters]
    if lengths:
        clauses.append("EXISTS (SELECT 1 FROM articles la WHERE la.article_id = c.article_id AND "
                       + " AND ".join(f"la.length_chars {op} ?" for op, _ in lengths) + ")")
        params.extend(value for _, value in lengths)
    if "category" in filters:
        clauses.append("EXISTS (SELECT 1 FROM article_categories ac WHERE "
                       "ac.article_id = c.article_id AND ac.category_name = ?)")
        params.append(filters["category"])
    if "linked_from" in filters:
        clauses.append("EXISTS (SELECT 1 FROM article_links l WHERE "
                       "l.source_article_id = ? AND l.target_article_id = c.article_id)")
        params.append(filters["linked_from"])
    return clauses, params


QUERY = object()  # placeholder for the query text or vector in a parameter list


def build_sql(method, filters, k, embedding_config=None):
    """Parameterized SELECT for one method; QUERY marks where the query value binds.

    The inner query ranks eligible chunks and applies LIMIT; metadata is joined afterwards so
    the join cannot stop the optimizer from reading vx_chunks_embedding.

    MariaDB 11.8 applies WHERE to a bounded HNSW candidate list, so an indexed query with
    predicates can return fewer than k eligible rows. Vector search therefore uses the index
    only without predicates; filtered vector search ranks every eligible row exactly.
    """
    clauses, params = eligible_sql(filters, embedding_config)
    if method == "keyword":
        match = "MATCH(c.text) AGAINST(? IN NATURAL LANGUAGE MODE)"
        score, hint, order = match, "", "score DESC, c.chunk_id"
        clauses.insert(0, match)
        params = [QUERY, QUERY, *params]
    else:
        distance = "VEC_DISTANCE_COSINE(c.embedding, VEC_FromText(?))"
        score = f"1 - {distance}"
        if method == "vector" and not clauses:
            hint, order = "", distance  # bare distance: the HNSW index can serve it
        else:
            hint, order = "IGNORE INDEX (vx_chunks_embedding) ", f"{distance}, c.chunk_id"
        params = [QUERY, *params, QUERY]
    inner = (f"SELECT c.chunk_id, c.article_id, c.revision_id, c.text, {score} AS score "
             f"FROM chunks c {hint}")
    if clauses:
        inner += "WHERE " + " AND ".join(clauses) + " "
    inner += f"ORDER BY {order} LIMIT ?"
    # FK chunks(article_id, revision_id) -> articles keeps every chunk on the current revision.
    sql = ("SELECT h.chunk_id, h.article_id, a.title, a.source_url, h.text, h.score "
           f"FROM ({inner}) h JOIN articles a "
           "ON a.article_id = h.article_id AND a.revision_id = h.revision_id "
           "ORDER BY h.score DESC, h.chunk_id")
    return sql, [*params, k]


def config_predicate(connection, embedding_config):
    """The config to filter on, or None when every chunk already has it (keeps the index).

    Without an explicit config, more than one stored configuration is ambiguous: hits would
    mix vector spaces and repeat passages, so that is an error rather than a guess.
    A requested config that no stored chunk has is also an error, not an empty result: the
    C05 hash covers device and library versions, so a query embedder that differs from the
    one that built the corpus must not silently match nothing.
    """
    cursor = connection.cursor()
    if embedding_config is None:
        cursor.execute("SELECT DISTINCT embedding_config FROM chunks LIMIT 2")
        if len(cursor.fetchall()) > 1:
            raise ValueError("chunks hold several embedding configurations; pass one")
        return None
    cursor.execute("SELECT DISTINCT embedding_config FROM chunks LIMIT 2")
    stored = [row[0] for row in cursor.fetchall()]
    if stored and embedding_config not in stored:
        cursor.execute("SELECT 1 FROM chunks WHERE embedding_config = ? LIMIT 1",
                       (embedding_config,))
        if not cursor.fetchall():
            raise ValueError(
                f"no chunks have embedding_config {embedding_config[:12]}…; re-embed the corpus "
                "with this model, device and library versions (python -m citehop.embed run), "
                "or search an existing config explicitly")
    return embedding_config if len(stored) > 1 else None


def bind(params, value):
    return [value if p is QUERY else p for p in params]


def vector_text(vector):
    values = [float(x) for x in vector]
    if len(values) != DIMENSIONS:
        raise ValueError(f"query vector has {len(values)} dimensions, expected {DIMENSIONS}")
    if not all(math.isfinite(x) for x in values) or not any(values):
        raise ValueError("query vector must be finite and nonzero")
    return json.dumps(values)


_embedder = None


def default_embedder(chunk_tokens=None, overlap_tokens=None):
    """(embed_query, embedding_config) from the C05 pinned BGE model, loaded once per process.

    The chunk sizes only select which stored configuration the query vector is compared with
    (S03 experiment databases); queries are embedded identically. None means the C05 default.
    """
    global _embedder
    if _embedder is None:
        try:
            from citehop.embed import Embedder

            _embedder = Embedder()
        except ImportError as exc:
            raise EmbedderUnavailable("vector search needs citehop.embed (C05) and the ml "
                                      f"extra: {exc}") from exc
    from citehop.embed import configs

    sizes = {key: value for key, value in (("chunk_tokens", chunk_tokens),
                                           ("overlap_tokens", overlap_tokens))
             if value is not None}
    return _embedder.embed_query, configs(_embedder.versions, **sizes)[1]


def search(query, method="vector", filters=None, k=5, *, connection=None, embedder=None,
           query_vector=None, embedding_config=None):
    """Ranked chunk hits from MariaDB. Raises ValueError for invalid input.

    Without `embedder`, vector methods use the C05 model and only its `embedding_config`.
    A custom `embedder(query) -> 768 floats` must match the given `embedding_config`;
    `query_vector` skips embedding (evaluation reuses one vector for ANN and exact runs).
    """
    query, filters = validate(query, method, filters, k)
    if method == "keyword":
        value = query
    else:
        if query_vector is None:
            if embedder is None:
                embedder, default_config = default_embedder()
                embedding_config = embedding_config or default_config
            query_vector = embedder(query)
        value = vector_text(query_vector)
    from citehop.db import connect

    with nullcontext(connection) if connection is not None else connect() as conn:
        sql, params = build_sql(method, filters, k, config_predicate(conn, embedding_config))
        cursor = conn.cursor()
        cursor.execute(sql, bind(params, value))
        rows = cursor.fetchall()
    return [Hit(chunk_id=r[0], article_id=int(r[1]), title=r[2], source_url=r[3], passage=r[4],
                rank=i, score=float(r[5]), method=method) for i, r in enumerate(rows, 1)]


def explain(method, filters, k, value, connection, embedding_config=None):
    """EXPLAIN rows (as dicts) for the same SQL `search` would run."""
    sql, params = build_sql(method, filters, k, config_predicate(connection, embedding_config))
    cursor = connection.cursor()
    cursor.execute("EXPLAIN " + sql, bind(params, value))
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def overlap_at_k(approximate, exact):
    """Share of exact top-k chunk IDs that the ANN result also returned (None if exact empty)."""
    truth = {h.chunk_id for h in exact}
    return len(truth & {h.chunk_id for h in approximate}) / len(truth) if truth else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m citehop.search")
    parser.add_argument("query")
    parser.add_argument("--method", choices=METHODS, default="vector")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--category")
    parser.add_argument("--min-length", type=int, dest="min_length_chars")
    parser.add_argument("--max-length", type=int, dest="max_length_chars")
    parser.add_argument("--linked-from", type=int, dest="linked_from")
    parser.add_argument("--embedding-config", help="restrict to one embedding configuration")
    parser.add_argument("--explain", action="store_true", help="also print the query plan")
    args = parser.parse_args(argv)
    filters = {key: getattr(args, key) for key in FILTER_KEYS if getattr(args, key) is not None}

    from citehop.db import connect

    try:
        query, filters = validate(args.query, args.method, filters, args.k)
        config, vector = args.embedding_config, None
        if args.method != "keyword":
            embed_query, model_config = default_embedder()
            config, vector = config or model_config, embed_query(query)
        with connect() as conn:
            hits = search(query, args.method, filters, args.k, connection=conn,
                          query_vector=vector, embedding_config=config)
            out = {"method": args.method, "filters": filters, "k": args.k,
                   "hits": [asdict(h) for h in hits]}
            if args.explain:
                value = query if vector is None else vector_text(vector)
                out["plan"] = explain(args.method, filters, args.k, value, conn, config)
    except (ValueError, EmbedderUnavailable) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
