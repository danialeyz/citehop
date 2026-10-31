# Retrieval and answer evaluation (C08)

`python -m citehop.evaluate` (or `make eval`) runs the frozen [question set](../eval/README.md) against the live MariaDB corpus through `search()` ([C06](RETRIEVAL.md)) and `answer()` ([C07](RAG.md)). Code: [`citehop/evaluate.py`](../citehop/evaluate.py). Tests: [`tests/test_evaluate.py`](../tests/test_evaluate.py).

## What a run does

| Split | Methods | Repetitions | Generation |
|---|---|---|---|
| dev (10) | keyword, ANN vector, exact | 1 | none |
| test (20) | keyword, vector | 3 per answerable question, 1 per unanswerable | 10 answers for review |

- **Recall@5 is article-level.** Chunk hits are deduplicated by each article's best chunk rank, then the first five distinct articles are scored against `relevant_article_ids`. The search asks for 50 chunks, then 100 (`search.MAX_K`), until five distinct articles appear. If fewer rows than requested come back, every eligible row was returned (`exhausted`); such questions count in `short_list`.
- Answerable questions with zero hits score 0 and stay in the denominator. Unanswerable questions have no labels, so they are reported separately and excluded from recall.
- Filtered and unfiltered questions are reported separately, and so is their latency. Filtered vector search is an exact scan (see [RETRIEVAL.md](RETRIEVAL.md#why-filtered-vector-search-does-not-use-the-hnsw-index)).
- **ANN vs exact (dev):** one query vector feeds both methods. The run records chunk overlap@5 and article overlap@5 for each question. Only the unfiltered cases test the HNSW index.
- **Timing boundaries:** `embedding_ms` is the BGE query embedding on CPU. `retrieval_ms` is `search()` with a precomputed vector at the evaluation's candidate depth, including the Python client round trip. `generation_ms` is the single Ollama call. Before any timed call, the run makes one untimed embedding, one untimed search per method and one untimed generator call. The manifest reports the median and nearest-rank p95 over every timed call, including repetitions.
- **Answers for review:** deterministic set of 10 test questions (the first 7 answerable and the first 3 unanswerable by ID). Each answer uses the first five chunks of the vector search. Review fields are `null` until a reviewer fills them in.

## Output

`results/runs/<UTC time>-<splits>-<config id>/`:

- `manifest.json` (schema `citehop-eval-v1`): run, corpus, embedding and config IDs; question-set hash and label-review counts; `final_claims_allowed`; MariaDB version and `mhnsw_ef_search`; generator, prompt version and limits; warm-up policy; latency units and boundaries; hardware; git commit and dirty flag; summary with denominators.
- `retrieval.jsonl`: one record per question repetition, holding every method's raw chunk ranks and scores, the article ranking, the depth attempts, timings and recall.
- `answers.json`: question, expected answer, full `answer()` output (sources, citations, usage, raw output) and empty review fields.

Absent values are `null`, never 0. For example, `answer_review.grounded` stays `null` until at least one answer is reviewed.

## Reviewing answers

In `answers.json`, a team member who did not write the answer sets `review.status` (`approved` or `needs_changes`), `grounded` and `citations_support` for answered cases, or `correct_abstention` for unanswerable ones. They also set `reviewer` and `reviewed_at`. `summarize()` then counts reviewed answers. Re-summarizing after review is a small call: `citehop.evaluate.summarize(records, answers)`.

## Provisional run, 2026-10-31

Run `20261031T162301Z-dev-test-15b1f5a1`: Apple M6, 24 GB, MariaDB 11.8.9 in local Docker, `corpus:2` (100 articles, 1,776 chunks, one embedding config), `mhnsw_ef_search` 20. **All 30 question labels are `unreviewed`, so these are harness results, not final claims** (`final_claims_allowed: false`).

| Split / method | Answerable n | Recall@5 all | unfiltered (n) | filtered (n) |
|---|---|---|---|---|
| dev keyword | 8 | 0.958 | 0.944 (6) | 1.0 (2) |
| dev vector (ANN) | 8 | 1.0 | 1.0 (6) | 1.0 (2) |
| dev exact | 8 | 1.0 | 1.0 (6) | 1.0 (2) |
| test keyword | 17 | 0.959 | 0.942 (12) | 1.0 (5) |
| test vector | 17 | 0.976 | 0.967 (12) | 1.0 (5) |

No answerable question had zero hits or a short list. Article rankings were identical across all three test repetitions. Misses: dev-05 keyword (2 of 3 articles), test-01 keyword (1 of 2), test-03 keyword (4 of 5) and test-03 vector (3 of 5). Unanswerable questions: 2 in dev and 3 in test, all of which returned hits, as expected.

On dev, ANN and exact agree completely: chunk overlap@5 is 1.0 on all 7 unfiltered cases (and on the 3 filtered cases, where the computation is the same). At the default `ef_search` there is no recall cost on this corpus, so the default stays.

| Latency (ms) | samples | median | p95 |
|---|---|---|---|
| test embedding | 54 | 12.9 | 18.6 |
| test keyword | 54 | 5.6 | 9.5 |
| test vector, unfiltered (ANN, 50 chunks) | 38 | 7.7 | 14.7 |
| test vector, filtered (exact scan) | 16 | 37.4 | 90.3 |
| dev exact, unfiltered | 7 | 184.8 | 265.5 |
| generation | 10 | 2,033 | 2,338 |

The dev latency rows have a single sample per question. The model answered all 7 answerable questions with valid labels and abstained (`insufficient_evidence`) on all 3 unanswerable ones. Grounding review: 0 of 10 reviewed (`grounded: null`).
