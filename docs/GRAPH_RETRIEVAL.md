# Graph-assisted retrieval experiment (S02)

Question: does following real Wikipedia links from the best vector hits find relevant articles that core vector retrieval misses? Code: [`citehop/graph_retrieval.py`](../citehop/graph_retrieval.py). Tests: [`tests/test_graph_retrieval.py`](../tests/test_graph_retrieval.py). Evidence: [`results/experiments/s02/20261101T141413Z-s02-dev-test-77fa2d52/`](../results/experiments/s02/20261101T141413Z-s02-dev-test-77fa2d52/manifest.json).

This is an experiment. The API, Search view and Graph view do not use it, and it does not change the core graph queries in `citehop/graph/queries.py`. Its runs are saved under `results/experiments/`, not `results/runs/`, so the Dashboard does not list them.

## Method

1. **Seeds (MariaDB).** Core `search(query, "vector", filters, k=100)` with the original filters. The first 10 distinct articles in rank order are the seeds.
2. **Expansion (Neo4j).** Only when graph status is `ready`. One Cypher read follows `LINKS_TO` one hop in either direction from the seeds. It returns at most 100 distinct non-seed articles; categories are not traversed. For each article, `support` is the number of distinct seeds it links to or is linked from. Self-links are ignored, and reciprocal or repeated edges count once. Neighbors are ordered by support (descending), then by the rank of the first seed they touch, then by `article_id`. The 100-article cap cuts this order and sets `truncated`. Statements use the C04 transaction timeout (5 s).
3. **Ranking (MariaDB).** One statement ranks the seed and neighbor chunks exactly: `cosine + 0.05 × support / seed_count`, with ties broken by `chunk_id`. The candidate list, the original category, length and linked-from `EXISTS` predicates and `LIMIT` are all in that statement. Neo4j does not know the filters, so the graph can narrow and reorder eligible rows, but it cannot add ineligible ones. Each chunk appears at most once.

The weight 0.05 was fixed before the first evaluation run and was not tuned. It is at most 0.05, so it only reorders articles with close cosine scores. Graph scores are specific to this method.

**Fallback.** If the graph is `stale`, `rebuilding` or `unavailable`, or if a Cypher read fails or times out, no graph data is used. The result is the core vector hits from step 1 (`method: "vector"`), with `used: false` and the reason. Stale graph data is never mixed into search evidence. Every result records `graph_version`, the seeds, the neighbors, `truncated`, missing seeds, and the time spent in each stage.

## Results

Run `20261101T141413Z-s02-dev-test-77fa2d52`, 2026-11-01. Live corpus `corpus:1` (content `d491fa4b…`), 1,776 chunks, embedding config `35e53e16…`. Graph `corpus:1` was `ready` before and after the run. Apple M6, MariaDB 11.8.9 and Neo4j 5.26.32 in local Docker. Both methods ran in one process with the same query vector. One untimed warm-up call per method came first. Test answerable questions ran 3 times. The vector numbers match the tracked C08 run `20261031T174404Z`.

| Split | Answerable | Recall@5, vector | Recall@5, graph | Graph higher / lower / equal |
|---|---|---|---|---|
| dev | 8 | 1.0 | 1.0 | 0 / 0 / 8 |
| test | 17 | 0.9765 | 0.9765 | 0 / 0 / 17 |

| Latency, median / p95 ms | Vector | Graph |
|---|---|---|
| test, all (n=54) | 9.7 / 79.7 | 199.8 / 265.7 |
| test, unfiltered (n=38) | 8.2 / 11.8 | 209.9 / 315.2 |
| test, filtered (n=16) | 39.0 / 99.1 | 93.1 / 216.3 |
| dev, all (n=10) | 8.7 / 248.3 | 203.8 / 483.1 |

Graph stages on the test split (n=20, last depth attempt): seed search 13.4 / 53.7 ms, Neo4j 7.4 / 11.1 ms, candidate ranking SQL 175.5 / 228.0 ms.

Expansion on the test split: 9.55 seeds and 68.6 neighbors on average (maximum 83). The cap was never reached, no seed was missing, and no query fell back. Across both splits, no neighbor article reached the graph top 5. Mean article overlap@5 with vector was 0.93 on test and 0.9 on dev, so the bonus only reordered articles that were already seeds.

**Finding.** On this corpus, graph expansion added no recall and cost about 25× the unfiltered latency (median 209.9 vs 8.2 ms). Neo4j is not the cost. The 100 articles are densely linked (917 links), so 10 seeds plus their neighbors cover about 78 of the 100 articles. The candidate step is therefore an exact cosine scan of most of the corpus, while core unfiltered search uses the HNSW index. Core vector Recall@5 is already 1.0 on dev and 0.98 on test, which leaves almost nothing to recover. A larger, sparser corpus might give a different result, but this run does not test that.

The question labels are not yet human-reviewed (`final_claims_allowed: false`), so these figures are provisional, like the C08 figures. This is a single run on one laptop, with no parameter sweep.

## Checks

| Check | Covered by |
|---|---|
| ≤ 10 seeds, ≤ 100 neighbors, out-of-range arguments rejected before any query | unit tests; Neo4j test with 150 linked articles: exactly 100 kept, `truncated`, same order on every call |
| Cycles, reciprocal links, self-links, shared categories | Neo4j test: cycle 1→2→3→1 plus 2→1 gives each neighbor once with the right support; a self-link is not a neighbor; an article that only shares a category with others has no neighbors |
| Deduplication | MariaDB test: 44 distinct chunks, no repeats from category or link joins |
| Original SQL filters | MariaDB tests: a neighbor that fails a category or linked-from + length filter never appears, even with the largest bonus; an eligible hit outside the global top-k is still found |
| Stale graph | unit tests (stale, rebuilding and unavailable statuses are never queried); Neo4j test with a mismatched source version |
| Outage | unit tests: a real refused Bolt connection, and a query timeout, both fall back to core vector hits |

## Commands

```bash
python -m citehop.graph_retrieval query "How does DBSCAN find clusters?" --k 5   # needs make venv-ml
make graph-retrieval-eval        # writes results/experiments/s02/<run_id>/; graph must be ready
make test                        # unit tests
CITEHOP_TEST_DB_NAME=citehop_test pytest tests/test_graph_retrieval.py -m db     # disposable DB
CITEHOP_TEST_NEO4J_URI=bolt://127.0.0.1:17687 CITEHOP_TEST_NEO4J_PASSWORD=test-pass \
  pytest tests/test_graph_retrieval.py -m neo4j                                  # disposable Neo4j
```
