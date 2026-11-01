"""S02 graph-assisted retrieval experiment: vector seeds, one Neo4j hop, MariaDB re-ranking.

    python -m citehop.graph_retrieval query "QUESTION" [--k N] [--category NAME]
                                    [--min-length N] [--max-length N] [--linked-from ID]
    python -m citehop.graph_retrieval eval [--splits dev test] [--repeats 3]
                                    [--out results/experiments/s02]

Pipeline (each step is bounded):

1. Seeds. Core `search(..., method="vector")` with the original filters returns up to
   SEED_CHUNKS chunks; the first MAX_SEEDS distinct articles, in rank order, are the seeds.
2. Expansion. If the graph status is `ready`, one Cypher statement follows LINKS_TO in either
   direction from the seeds and returns at most MAX_NEIGHBORS distinct non-seed articles.
   Categories are not traversed. `support` is the number of distinct seeds an article is
   linked to or from (self-links and duplicate/reciprocal edges count once). Neighbors are
   ordered by support DESC, first linked seed's rank, article_id; the cap cuts that order.
3. Ranking in MariaDB. Chunks of seed and neighbor articles are ranked exactly by
   cosine + GRAPH_WEIGHT * support / seed_count, ties by chunk_id, with the original category,
   length and linked-from predicates and LIMIT in the same statement. Neo4j does not know the
   filters, so a neighbor that fails them is dropped here, never returned.

GRAPH_WEIGHT was fixed before any evaluation run and is not tuned. The bonus is at most
GRAPH_WEIGHT, so it only reorders articles whose cosine scores are close. Scores are specific
to this method and not comparable with core vector scores.

When the graph is stale, rebuilding or unavailable, or a graph query fails or times out, the
result falls back to the seed search (core vector hits) and says so; stale graph data is
never mixed into search evidence. This is an experiment: the API and the Graph view do not
use it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from citehop.search import (
    FILTER_KEYS,
    MAX_K,
    QUERY,
    Hit,
    bind,
    config_predicate,
    eligible_sql,
    search,
    validate,
    vector_text,
)

MAX_SEEDS = 10
MAX_NEIGHBORS = 100
SEED_CHUNKS = MAX_K  # seed search depth in chunks (ANN or exact, as in core search)
GRAPH_WEIGHT = 0.05
METHOD = "graph"

SEEDS_PRESENT = """
MATCH (s:CiteHop:Article)
WHERE s.uid IN $seeds
RETURN s.article_id AS article_id
"""

# Seeds come first so the LIMIT budget (seeds + neighbors + 1) always covers every seed row.
EXPAND = """
UNWIND range(0, size($seeds) - 1) AS i
MATCH (s:CiteHop:Article {uid: $seeds[i]})-[:LINKS_TO]-(n:CiteHop:Article)
WHERE n.uid <> s.uid
WITH n, n.uid IN $seeds AS is_seed, count(DISTINCT s) AS support, min(i) AS first_seed
ORDER BY is_seed DESC, support DESC, first_seed, n.article_id
LIMIT $limit
RETURN n.article_id AS article_id, is_seed, support, first_seed
"""


@dataclass(frozen=True)
class Expansion:
    """Graph step outcome. `support` covers seeds (linked to other seeds) and neighbors."""

    status: str
    graph_version: str | None
    used: bool
    fallback_reason: str | None = None
    seeds: tuple[int, ...] = ()
    seeds_missing: tuple[int, ...] = ()
    neighbors: tuple[int, ...] = ()
    support: dict[int, int] = field(default_factory=dict)
    truncated: bool = False


@dataclass(frozen=True)
class GraphSearchResult:
    hits: list[Hit]
    expansion: Expansion
    timings_ms: dict[str, float]
    provenance: dict[int, dict]  # article_id -> {"role", "support", "bonus"} for returned hits

    def to_dict(self):
        return {"hits": [asdict(h) for h in self.hits], "graph": asdict(self.expansion),
                "timings_ms": self.timings_ms,
                "provenance": {str(a): p for a, p in self.provenance.items()}}


def seed_articles(hits, max_seeds=MAX_SEEDS):
    """Distinct article IDs in order of their best chunk rank, at most `max_seeds`."""
    seeds = []
    for hit in sorted(hits, key=lambda h: h.rank):
        if hit.article_id not in seeds:
            seeds.append(hit.article_id)
            if len(seeds) == max_seeds:
                break
    return seeds


def _uid(article_id):
    from citehop.graph.store import article_uid

    return article_uid(article_id)


def expand(graph, seeds, max_neighbors=MAX_NEIGHBORS):
    """One undirected LINKS_TO hop from `seeds` through `graph` (a GraphQueries).

    Never raises for graph problems: a graph that is not `ready`, or a failing query, gives an
    Expansion with used=False and the reason.
    """
    if not 1 <= len(seeds) <= MAX_SEEDS or len(set(seeds)) != len(seeds):
        raise ValueError(f"seeds must be 1..{MAX_SEEDS} distinct article IDs")
    if type(max_neighbors) is not int or not 0 <= max_neighbors <= MAX_NEIGHBORS:
        raise ValueError(f"max_neighbors must be an integer from 0 to {MAX_NEIGHBORS}")
    if graph is None:
        return Expansion("unavailable", None, False, "no graph configured", tuple(seeds))
    from citehop.graph.store import GraphError, run

    status = graph.status()
    if status.status != "ready":
        return Expansion(status.status, status.imported_version, False,
                         f"graph is {status.status}: {status.detail}", tuple(seeds))
    uids = [_uid(a) for a in seeds]

    def read(cypher, params):
        return run(graph.driver, cypher, params, timeout=graph.timeout, database=graph.database)

    try:
        present = {r["article_id"] for r in read(SEEDS_PRESENT, {"seeds": uids})}
        rows = read(EXPAND, {"seeds": uids, "limit": len(seeds) + max_neighbors + 1})
    except GraphError as exc:
        return Expansion("unavailable", status.imported_version, False,
                         f"{type(exc).__name__}: {exc}", tuple(seeds))
    support = {r["article_id"]: r["support"] for r in rows if r["is_seed"]}
    neighbor_rows = [r for r in rows if not r["is_seed"]]
    truncated = len(neighbor_rows) > max_neighbors
    neighbor_rows = neighbor_rows[:max_neighbors]
    support.update({r["article_id"]: r["support"] for r in neighbor_rows})
    return Expansion(
        status.status, status.imported_version, True, None, tuple(seeds),
        tuple(a for a in seeds if a not in present),
        tuple(r["article_id"] for r in neighbor_rows), support, truncated)


def bonuses(expansion):
    """article_id -> GRAPH_WEIGHT * support / seed count, only for nonzero support."""
    n = len(expansion.seeds)
    return {a: GRAPH_WEIGHT * s / n for a, s in sorted(expansion.support.items()) if s}


def build_sql(filters, articles, bonus, k, embedding_config=None):
    """Parameterized exact ranking over the candidate articles' eligible chunks.

    The candidate list, the original filters and the LIMIT are all in one statement, so the
    graph can only narrow and reorder eligible rows; Python never filters a top-k.
    """
    if not articles:
        raise ValueError("no candidate articles")
    clauses, params = eligible_sql(filters, embedding_config)
    ids = sorted(set(articles))
    clauses.insert(0, f"c.article_id IN ({', '.join('?' * len(ids))})")
    params = [*ids, *params]
    weights = [(a, float(b)) for a, b in sorted(bonus.items()) if b and a in set(ids)]
    case = ("CASE c.article_id " + " ".join("WHEN ? THEN ?" for _ in weights) + " ELSE 0 END"
            if weights else "0")
    inner = ("SELECT c.chunk_id, c.article_id, c.revision_id, c.text, "
             "1 - VEC_DISTANCE_COSINE(c.embedding, VEC_FromText(?)) AS cosine, "
             f"{case} AS bonus FROM chunks c IGNORE INDEX (vx_chunks_embedding) "
             "WHERE " + " AND ".join(clauses))
    sql = ("SELECT h.chunk_id, h.article_id, a.title, a.source_url, h.text, "
           "h.cosine + h.bonus AS score, h.cosine, h.bonus "
           f"FROM ({inner}) h JOIN articles a "
           "ON a.article_id = h.article_id AND a.revision_id = h.revision_id "
           "ORDER BY score DESC, h.chunk_id LIMIT ?")
    return sql, [QUERY, *(x for pair in weights for x in pair), *params, k]


def graph_search(query, filters=None, k=5, *, graph, connection=None, query_vector=None,
                 embedder=None, embedding_config=None, max_seeds=MAX_SEEDS,
                 max_neighbors=MAX_NEIGHBORS):
    """Graph-assisted hits for `query`, or the core vector hits when the graph cannot be used."""
    query, filters = validate(query, "vector", filters, k)
    if type(max_seeds) is not int or not 1 <= max_seeds <= MAX_SEEDS:
        raise ValueError(f"max_seeds must be an integer from 1 to {MAX_SEEDS}")
    if query_vector is None:
        if embedder is None:
            from citehop.search import default_embedder

            embedder, default_config = default_embedder()
            embedding_config = embedding_config or default_config
        query_vector = embedder(query)
    value = vector_text(query_vector)
    from citehop.db import connect

    timings = {}
    with nullcontext(connection) if connection is not None else connect() as conn:
        started = time.perf_counter()
        seed_hits = search(query, "vector", filters, SEED_CHUNKS, connection=conn,
                           query_vector=query_vector, embedding_config=embedding_config)
        timings["seed_ms"] = _ms(started)
        seeds = seed_articles(seed_hits, max_seeds)
        if not seeds:  # nothing eligible: the graph cannot add eligible rows either
            expansion = Expansion("not_queried", None, False, "no eligible seed hits")
        else:
            started = time.perf_counter()
            expansion = expand(graph, seeds, max_neighbors)
            timings["graph_ms"] = _ms(started)
        if not expansion.used:
            hits = seed_hits[:k]  # core vector hits, method "vector"
            provenance = {h.article_id: {"role": "seed", "support": None, "bonus": None}
                          for h in hits}
            return GraphSearchResult(hits, expansion, timings, provenance)
        bonus = bonuses(expansion)
        sql, params = build_sql(filters, [*expansion.seeds, *expansion.neighbors], bonus, k,
                                config_predicate(conn, embedding_config))
        started = time.perf_counter()
        cursor = conn.cursor()
        cursor.execute(sql, bind(params, value))
        rows = cursor.fetchall()
        timings["candidate_ms"] = _ms(started)
    hits = [Hit(chunk_id=r[0], article_id=int(r[1]), title=r[2], source_url=r[3], passage=r[4],
                rank=i, score=float(r[5]), method=METHOD) for i, r in enumerate(rows, 1)]
    seeds = set(expansion.seeds)
    provenance = {h.article_id: {"role": "seed" if h.article_id in seeds else "neighbor",
                                 "support": expansion.support.get(h.article_id, 0),
                                 "bonus": bonus.get(h.article_id, 0.0)} for h in hits}
    return GraphSearchResult(hits, expansion, timings, provenance)


def _ms(started):
    return round((time.perf_counter() - started) * 1000, 3)


# ---------- comparison with core vector retrieval ----------

SCHEMA = "citehop-s02-v1"
BOUNDARIES = {
    "embedding_ms": "embed_query(question), shared by both methods",
    "retrieval_ms_vector": "core search(method='vector') with the precomputed vector; summed "
                           "over candidate-depth attempts",
    "retrieval_ms_graph": "graph_search() with the same vector: seed SQL + graph status + "
                          "Neo4j expansion + candidate SQL; summed over candidate-depth attempts",
    "stage_ms": "graph_search stages of the last candidate-depth attempt: seed_ms (core vector "
                "search, 100 chunks), graph_ms (status check + two Cypher reads), candidate_ms "
                "(exact ranking SQL)",
}


def compare(questions, *, run_vector, run_graph, embed_fn, splits=("dev", "test"), repeats=3,
            log=None):
    """Per-question records for core vector and graph-assisted retrieval.

    run_vector(question, filters, depth, vector) -> hit dicts;
    run_graph(question, filters, depth, vector) -> (hit dicts, expansion dict with stage_ms).
    Test answerable questions repeat `repeats` times for latency, as in C08.
    """
    from citehop.evaluate import WARMUP_QUERY, K, recall_at_k, retrieve_articles

    vector = embed_fn(WARMUP_QUERY)  # untimed warm-up of model, MariaDB and Neo4j
    run_vector(WARMUP_QUERY, {}, K, vector)
    run_graph(WARMUP_QUERY, {}, K, vector)
    records = []
    for q in sorted((q for q in questions if q["split"] in splits), key=lambda q: q["id"]):
        reps = repeats if q["split"] == "test" and q["answerable"] else 1
        for rep in range(1, reps + 1):
            started = time.perf_counter()
            vector = embed_fn(q["question"])
            record = {"question_id": q["id"], "split": q["split"], "repetition": rep,
                      "answerable": q["answerable"], "filters": q["filters"],
                      "filtered": bool(q["filters"]),
                      "relevant_article_ids": q["relevant_article_ids"],
                      "embedding_ms": _ms(started), "methods": {}}
            graph_info = []

            def graph_depth(depth, q=q, v=vector, out=graph_info):
                hits, expansion = run_graph(q["question"], q["filters"], depth, v)
                out.append(expansion)
                return hits

            for method, fn in (("vector", lambda d, q=q, v=vector:
                                run_vector(q["question"], q["filters"], d, v)),
                               ("graph", graph_depth)):
                hits, ranking, info = retrieve_articles(fn)
                record["methods"][method] = {
                    **info, "recall_at_5": recall_at_k(ranking, q["relevant_article_ids"]),
                    "article_ranking": ranking,
                    "hits": [{k: h[k] for k in ("chunk_id", "article_id", "rank", "score")}
                             for h in hits]}
            record["methods"]["graph"]["expansion"] = graph_info[-1]
            records.append(record)
            if log:
                exp = graph_info[-1]
                log(f"{q['id']} rep {rep}: vector R@5={record['methods']['vector']['recall_at_5']}"
                    f" graph R@5={record['methods']['graph']['recall_at_5']} "
                    f"({len(exp['seeds'])} seeds, {len(exp['neighbors'])} neighbors"
                    f"{', fallback' if not exp['used'] else ''})")
    return records


def summarize(records):
    from citehop.evaluate import first_articles, latency, mean, recall_group

    summary = {"retrieval": {}, "graph": {}, "latency": {}}
    for split in sorted({r["split"] for r in records}):
        rows = [r for r in records if r["split"] == split]
        first = [r for r in rows if r["repetition"] == 1]
        positive = [r for r in first if r["answerable"]]
        summary["retrieval"][split] = {m: {
            "all_answerable": recall_group(positive, m),
            "unfiltered": recall_group([r for r in positive if not r["filtered"]], m),
            "filtered": recall_group([r for r in positive if r["filtered"]], m),
        } for m in ("vector", "graph")}
        pairs = [(r["methods"]["vector"]["recall_at_5"], r["methods"]["graph"]["recall_at_5"])
                 for r in positive]
        summary["retrieval"][split]["per_question"] = {
            "graph_higher": sum(g > v for v, g in pairs),
            "graph_lower": sum(g < v for v, g in pairs), "equal": sum(g == v for v, g in pairs)}
        expansions = [r["methods"]["graph"]["expansion"] for r in first]
        used = [e for e in expansions if e["used"]]
        summary["graph"][split] = {
            "questions": len(first), "expanded": len(used),
            "fallbacks": dict(Counter(e["status"] for e in expansions if not e["used"])),
            "graph_versions": sorted({e["graph_version"] for e in used}),
            "mean_seeds": mean([len(e["seeds"]) for e in used]),
            "mean_neighbors": mean([len(e["neighbors"]) for e in used]),
            "max_neighbors": max((len(e["neighbors"]) for e in used), default=None),
            "truncated": sum(e["truncated"] for e in used),
            "seeds_missing": sum(len(e["seeds_missing"]) for e in used),
            "mean_article_overlap_at_5": mean([
                len(first_articles(r["methods"]["vector"]) & first_articles(r["methods"]["graph"]))
                / 5 for r in first if r["methods"]["vector"]["article_ranking"]]),
            **{f"stage_{key}": latency([e["stage_ms"].get(key) for e in used])
               for key in ("seed_ms", "graph_ms", "candidate_ms")},
            "neighbor_articles_in_top_5": sum(
                len(first_articles(r["methods"]["graph"])
                    & set(r["methods"]["graph"]["expansion"]["neighbors"])) for r in first),
        }
        summary["latency"][split] = {
            "samples": {"questions": len(first), "records": len(rows)},
            "embedding_ms": latency([r["embedding_ms"] for r in rows]),
            **{f"retrieval_ms_{m}{suffix}": latency([r["methods"][m]["retrieval_ms"]
                                                     for r in subset])
               for m in ("vector", "graph")
               for suffix, subset in (("", rows),
                                      ("_unfiltered", [r for r in rows if not r["filtered"]]),
                                      ("_filtered", [r for r in rows if r["filtered"]]))}}
    return summary


def eval_main(args):
    from citehop.db import connect, graph_driver
    from citehop.evaluate import database_state, git_state, hardware
    from citehop.graph.__main__ import source_version
    from citehop.graph.queries import GraphQueries
    from citehop.search import default_embedder

    document = json.loads(args.questions.read_text())
    questions = document["questions"]
    label_review = Counter(q["review"]["status"] for q in questions)
    final = all(q["review"]["status"] == "approved" for q in questions)
    embed_query, embedding_config = default_embedder()
    created = datetime.now(UTC)

    def log(message):
        print(message, file=sys.stderr)

    driver = graph_driver()
    try:
        graph = GraphQueries(driver, source_version)
        status_before = graph.status()
        if status_before.status != "ready":
            log(f"graph is {status_before.status}: {status_before.detail}; run make graph-import")
            return 1
        with connect() as conn:
            state = database_state(conn)
            if state["corpus"]["source_corpus_id"] != document["corpus_id"]:
                log("questions were written for a different corpus snapshot")
                return 1

            def run_vector(query, filters, depth, vector):
                return [asdict(h) for h in search(query, "vector", filters, depth,
                                                  connection=conn, query_vector=vector,
                                                  embedding_config=embedding_config)]

            def run_graph(query, filters, depth, vector):
                result = graph_search(query, filters, depth, graph=graph, connection=conn,
                                      query_vector=vector, embedding_config=embedding_config)
                return [asdict(h) for h in result.hits], {**asdict(result.expansion),
                                                          "stage_ms": result.timings_ms}

            records = compare(questions, run_vector=run_vector, run_graph=run_graph,
                              embed_fn=embed_query, splits=tuple(args.splits),
                              repeats=args.repeats, log=log)
        status_after = graph.status()
    finally:
        driver.close()

    from citehop.embed import MODEL_ID, MODEL_REVISION

    config = {
        "k": 5, "max_seeds": MAX_SEEDS, "max_neighbors": MAX_NEIGHBORS,
        "seed_chunks": SEED_CHUNKS, "graph_weight": GRAPH_WEIGHT,
        "expansion": "one undirected LINKS_TO hop; categories not traversed",
        "ranking": "exact cosine + graph_weight * support / seeds; ties by chunk_id",
        "baseline": "core search(method='vector')", "test_repeats": args.repeats,
        "embedding_model": MODEL_ID, "embedding_model_revision": MODEL_REVISION,
        "embedding_config": embedding_config, "mariadb": state["mariadb"],
        "graph_version": status_before.imported_version,
    }
    config_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    run_id = f"{created:%Y%m%dT%H%M%SZ}-s02-{'-'.join(args.splits)}-{config_id[:8]}"
    out = args.out / run_id
    out.mkdir(parents=True, exist_ok=False)
    with (out / "retrieval.jsonl").open("w") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "schema": SCHEMA, "card": "S02", "run_id": run_id,
        "created_at": created.isoformat(timespec="seconds"),
        "status": "final" if final else "provisional: question labels are not all approved",
        "final_claims_allowed": final,
        "question_set": {"path": str(args.questions), "corpus_id": document["corpus_id"],
                         "labels_sha256": document["labels_sha256"],
                         "label_review": dict(label_review)},
        "splits": {s: sum(q["split"] == s for q in questions) for s in args.splits},
        "corpus": state["corpus"], "chunk_configs": state["chunk_configs"],
        "graph": {"before": asdict(status_before), "after": asdict(status_after)},
        "config_id": config_id, "config": config,
        "warm_up": "one untimed embedding, vector search and graph search before timed calls; "
                   "one process, one MariaDB connection, one Neo4j driver",
        "latency": {"unit": "ms", "boundaries": BOUNDARIES,
                    "statistics": "median and nearest-rank p95 over every timed call"},
        "hardware": hardware(), "code": git_state(),
        "files": {"retrieval": "retrieval.jsonl"},
        "summary": summarize(records),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                                                  default=str) + "\n")
    print(out)
    return 0


def query_main(args):
    from citehop.db import connect, graph_driver
    from citehop.graph.__main__ import source_version
    from citehop.graph.queries import GraphQueries
    from citehop.search import EmbedderUnavailable

    filters = {key: getattr(args, key) for key in FILTER_KEYS if getattr(args, key) is not None}
    try:
        driver = graph_driver()
    except KeyError:  # NEO4J_PASSWORD unset: no graph, core vector fallback
        driver = None
    try:
        graph = GraphQueries(driver, source_version) if driver else None
        with connect() as conn:
            result = graph_search(args.query, filters, args.k, graph=graph, connection=conn)
    except (ValueError, EmbedderUnavailable) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
        return 1
    finally:
        if driver:
            driver.close()
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m citehop.graph_retrieval")
    sub = parser.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("query", help="one graph-assisted search")
    q.add_argument("query")
    q.add_argument("--k", type=int, default=5, choices=range(1, MAX_K + 1), metavar="K")
    q.add_argument("--category")
    q.add_argument("--min-length", type=int, dest="min_length_chars")
    q.add_argument("--max-length", type=int, dest="max_length_chars")
    q.add_argument("--linked-from", type=int, dest="linked_from")
    e = sub.add_parser("eval", help="compare with core vector retrieval on the frozen questions")
    e.add_argument("--questions", type=Path, default=Path("eval/questions.json"))
    e.add_argument("--splits", nargs="+", choices=("dev", "test"), default=["dev", "test"])
    e.add_argument("--repeats", type=int, default=3)
    e.add_argument("--out", type=Path, default=Path("results/experiments/s02"))
    args = parser.parse_args(argv)
    return query_main(args) if args.cmd == "query" else eval_main(args)


if __name__ == "__main__":
    sys.exit(main())
