# Native retrieval and SQL filtering (C06)

Retrieval runs entirely in MariaDB over the [C03 tables](DATA_MODEL.md). It never opens a Neo4j connection, so search works when the graph is down. Code: [`citehop/search.py`](../citehop/search.py). Tests: [`tests/test_search.py`](../tests/test_search.py).

```python
from citehop.search import search
search("How does DBSCAN find clusters?", method="vector",
       filters={"category": "Cluster analysis algorithms"}, k=5)
# -> [Hit(chunk_id, article_id, title, source_url, passage, rank, score, method), ...]
```

## Methods

| `method` | SQL | `score` | Index |
|---|---|---|---|
| `keyword` | `MATCH(text) AGAINST(? IN NATURAL LANGUAGE MODE)` | InnoDB FULLTEXT relevance (not BM25) | `ft_chunks_text` |
| `vector` | `ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText(?)) LIMIT k` | cosine similarity, `1 − distance` | `vx_chunks_embedding` only when unfiltered (see below) |
| `exact` | same distance, `IGNORE INDEX (vx_chunks_embedding)`, sorts every eligible row | cosine similarity | none (baseline) |

Scores are specific to each method. They are not probabilities and must not be compared across methods.

## Input and result rules

- `query` is a non-empty string of at most 1,000 characters, and `k` is an integer from 1 to 100. Filters are limited to `category` (exact name), `min_length_chars` and `max_length_chars` (`articles.length_chars`, inclusive), and `linked_from` (article ID: hits are articles that this article links to). These are the keys used in `eval/questions.json`. Any other value raises `ValueError` before the embedder or the database is called.
- All values are bound parameters. Hostile strings in the query or in a category are treated as data.
- Filters are SQL `EXISTS` predicates inside the ranked subquery, which is evaluated before `LIMIT`. Python never filters a global top-k. Because they are `EXISTS` predicates, a chunk appears at most once even if its article has many categories or links.
- Metadata (`title`, `source_url`) is joined after the `LIMIT` on `(article_id, revision_id)`. The C03 foreign key keeps every chunk on its article's current revision.
- Ordering: `score DESC, chunk_id`. Keyword and exact results are fully deterministic. ANN ties at the `k` boundary depend on the HNSW traversal.
- Vector methods embed with the C05 query embedder, which applies the BGE query instruction. Only chunks with that embedder's `embedding_config` are searched. If no config is given and the table holds more than one, the search raises an error instead of mixing vector spaces. If chunks exist but none has the requested config, the search also raises an error instead of returning nothing. The C05 hash includes the device and the torch/transformers/tokenizers versions, so the query embedder (CPU) must match how the corpus was embedded; re-embed with `python -m citehop.embed run` after changing either. `query_vector=` lets an evaluation embed once and run both `vector` and `exact`.

## Why filtered vector search does not use the HNSW index

On MariaDB 11.8.9, the vector index returns a bounded candidate list (sized by `mhnsw_ef_search`, default 20), and `WHERE` is applied to that list afterwards. Observed on the fixture database with `FORCE INDEX (vx_chunks_embedding) WHERE article_id = X` for an article with 3 chunks: `LIMIT 3` returned 1 row, `LIMIT 5` returned 2, and `LIMIT 50` returned 3. A filtered indexed query would therefore filter a global top-k without warning. Two rules follow:

1. Unfiltered vector search uses the index. The ANN subquery reads only `chunks`, because joining `articles` inside it made the optimizer drop the index and use filesort.
2. Vector search with any predicate (including an `embedding_config` that not every chunk has) uses `IGNORE INDEX`. It then computes exact cosine over the eligible rows, which the optimizer reaches through the category, link, or length index. For filtered queries, `vector` and `exact` are therefore the same computation.

## Runnable SQL examples and observed plans

`python -m citehop.apply_sql sql/search_examples.sql` runs [three examples](../sql/search_examples.sql). Each one prints its `EXPLAIN` output and then its rows. The query vector is a stored chunk of *Perceptron*, so no embedder is needed.

Plans observed on 2026-10-31 on the live corpus (MariaDB 11.8.9, 100 articles, 1,776 C05 chunks, one embedding config):

| Example | Plan (derived subquery) | Scan? |
|---|---|---|
| 1. Keyword `cluster centroids`, category *Cluster analysis algorithms* | `c` `fulltext` via `ft_chunks_text`; `ac` `eq_ref` via `idx_categories_name`; temporary + filesort of the matches | Fulltext index lookup, no table scan; it sorts only the matching rows |
| 2. Vector, unfiltered, k=5 | `c` `index` via `vx_chunks_embedding` (estimated rows 955), no filesort | ANN index |
| 3. Vector, `linked_from` 22212276 (*Ensemble learning*), `max_length_chars` 30000 | `l` `ref` via `PRIMARY` (17 links) → `la` `eq_ref` → `c` `ref` via `uq_chunks_position`; filesort | **Scans every eligible chunk** (exact cosine over the linked articles' chunks) |

The same plans appear on the fixture database (below) and through `python -m citehop.search … --explain`. With a category filter, the vector query reads `ac` via `idx_categories_name` and then `c` via `uq_chunks_position`, which is also an exact scan of the eligible rows.

## Indexed vs exact retrieval

| Data | Queries | ANN ∩ exact overlap@5 | Median latency, warm, one run each |
|---|---|---|---|
| Live corpus, BGE embeddings, draft dev questions (7 unfiltered, 3 filtered) | 10 | 1.0 on all 10 | vector 2.0 ms, exact 159.2 ms, keyword 4.7 ms, query embedding 35.4 ms |
| Fixture: real articles, 2,104 random unit vectors, seeded random queries, `mhnsw_ef_search`=20 (default) | 50 | mean 0.504, min 0.2 | vector 2.6 ms, exact 88.8 ms |
| same, `mhnsw_ef_search`=100 | 50 | mean 0.912, min 0.6 | vector 2.1 ms, exact 77.2 ms |
| same, `mhnsw_ef_search`=400 | 50 | mean 0.996, min 0.8 | vector 2.6 ms, exact 81.5 ms |

The tests ran on an Apple M6 development Mac, with client and Docker MariaDB on the same machine. Latency includes the Python client round trip. These are smoke observations, not C08 results: the labels are unreviewed drafts, each query ran once, and there was no warm-up policy. Isotropic random vectors are the worst case for HNSW, while real embeddings cluster. C08 measures recall on the dev split and decides whether `mhnsw_ef_search` needs raising. The defaults are unchanged here.

On the live corpus, the query *Which algorithm groups points by density?* with `max_length_chars` 6000 returned five hits for both `vector` and `exact`. None of the five is in the unfiltered exact top 20, so the filter is applied before the limit.

## Reciprocal rank fusion (S01)

`method="hybrid"` runs `keyword` and `vector` at depth 50 on one connection, with the same filters and `embedding_config`, then fuses them with reciprocal rank fusion: `score = Σ 1 / (60 + rank)` over the lists that contain the chunk. The constant (60) and the depth (50) are fixed; no sweep was run. Sums are exact fractions, so equal sums tie exactly and ties break on `chunk_id`, as in SQL. A hybrid hit has the usual fields (`score` is the RRF sum, `method` is `hybrid`) plus `sources`, which lists `(method, rank, score)` for each input list that ranked it. The API does not expose `hybrid`; it is available from Python, the CLI and `python -m citehop.evaluate --hybrid`.

Frozen-set comparison, run `20261101T140542Z-dev-test-211053ad` (Apple M6, MariaDB 11.8.9 in local Docker, `corpus:1` with 100 articles and 1,776 chunks, `mhnsw_ef_search` 20, no answers generated). Labels are still unreviewed, so these are provisional.

| Recall@5 (answerable n) | keyword | vector | hybrid |
|---|---|---|---|
| dev (8) | 0.958 | 1.0 | 1.0 |
| test (17) | 0.959 | 0.976 | 0.988 |

| Retrieval latency, test (ms, median / p95) | keyword | vector | hybrid |
|---|---|---|---|
| unfiltered (38 calls) | 4.96 / 7.09 | 6.77 / 8.86 | 11.26 / 16.95 |
| filtered (16 calls) | 4.55 / 6.23 | 30.26 / 74.83 | 39.16 / 78.70 |

Hybrid recovers both keyword misses that vector already got (dev-05, test-01). On test-03 it scores 0.8, against 0.8 for keyword and 0.6 for vector. Its retrieval latency is roughly the sum of its two queries. Query embedding (median 12.4 ms on test) is excluded from these timings, as for `vector`.

## Commands

```bash
python -m citehop.search "k-means initialization" --method keyword --k 5 --category "Cluster analysis algorithms"
python -m citehop.search "How does DBSCAN find clusters?" --method vector --explain   # needs make venv-ml
python -m citehop.search "How does DBSCAN find clusters?" --method hybrid --k 5
python -m citehop.evaluate --hybrid --no-answers                                      # S01 comparison
python -m citehop.apply_sql sql/search_examples.sql
CITEHOP_TEST_DB_NAME=citehop_test pytest tests/test_search.py         # db tests need a disposable DB
CITEHOP_TEST_DB_NAME=citehop_test python scripts/search_fixture.py     # realistic plan fixture
CITEHOP_TEST_DB_NAME=citehop_test python scripts/search_fixture.py --compare 50
```

Vector methods import `citehop.embed` (C05) lazily and need `make venv-ml`. Without the ml extra, they raise `EmbedderUnavailable`, and keyword search still works.
