# One chunk-size experiment (S03)

Does 200-token chunking (overlap 50) retrieve better than the 300/50 default? This was decided on the **dev split only**, by a rule written in code before the dev runs (not committed first; see [Pre-registered rule](#pre-registered-rule)). One labeled test run of the chosen setting followed. Code: [`citehop/chunk_experiment.py`](../citehop/chunk_experiment.py). Tests: [`tests/test_chunk_experiment.py`](../tests/test_chunk_experiment.py), plus one DB test in `tests/test_embed_db.py`. Evidence: [`results/experiments/s03-chunking/`](../results/experiments/s03-chunking/).

**Result: keep 300/50.** On dev, 200/50 has the same vector Recall@5 (1.0 both). It costs 65% more chunks and 12% more embedded tokens, and makes exact scans about 60% slower. The demo configuration is unchanged.

## Isolation

Each arm has its own MariaDB database on a separate Compose project, so the demo database and its chunks are never read or written:

| Arm | Database | Chunking | `embedding_config` |
|---|---|---|---|
| 300-50 (baseline) | `citehop_s03_300` | 300 / 50 | `35e53e16…` (the same hash as the C05–C14 demo corpus) |
| 200-50 (candidate) | `citehop_s03_200` | 200 / 50 | `d842c313…` |

The two arms are the same in everything else:

- **Corpus.** Both load the pinned snapshot (`full.json` SHA-256 `202568aa…`, checked offline against `eval/corpus.json`). Both have the same content, `d491fa4b…`: 100 articles and 917 links.
- **Model.** BGE base v1.5 @ `a5beb1e3…`, run on CPU.
- **Questions.** Both use `eval/questions.json` (labels `23e52d6a…`).
- **Code path.** Both use the C08 evaluator. `freeze` refuses to compare runs that differ in corpus, labels or model.

Non-default sizes are only exposed as CLI flags: `citehop.embed run --chunk-tokens`, and `citehop.evaluate --chunk-tokens`, which selects which stored configuration to query. Defaults are unchanged. Running `--chunk-tokens 200` against the demo database would replace its chunks, so the experiment always sets `DB_NAME` per arm.

## Pre-registered rule

This rule was written as `chunk_experiment.RULE` before the first dev run, then copied verbatim into `decision.json` by `freeze`, after the dev runs. It was not committed before measuring: the runs record `code.dirty: true`, and `decision.json` (frozen 14:15:18Z) is later than every dev run. The saved evidence therefore cannot prove that the rule came first; it shows only that the rule was fixed before any test run.

The rule:

> Primary metric: dev vector (ANN) article Recall@5 over all answerable questions. Adopt 200/50 only if its primary metric is strictly higher than 300/50 and its dev keyword Recall@5 is not lower. Otherwise keep 300/50, the current default, which has fewer chunks to embed and store. Chunk count, embedding effort and latency are recorded but do not decide: one laptop, few samples. The test split is never used for the choice.

Order is enforced in code:

- `freeze` refuses once any test run exists.
- `decision.json` is created exclusively and never rewritten.
- `dev` refuses after the freeze.
- `test` refuses before the freeze, and refuses a second run.
- The test manifest's `label` carries the decision file's SHA-256.

## Reproduce

```bash
# separate Compose project/port in .env (here COMPOSE_PROJECT_NAME=citehop-madrid-s03, DB_PORT=3327)
docker compose --env-file .env -f docker/docker-compose.yml up -d --wait db
# as MariaDB root: CREATE DATABASE citehop_s03_200; GRANT ALL ON citehop_s03_200.* TO 'citehop'@'%';
python -m citehop.acquire fetch --subset full          # reuses/validates the pinned cache
for db in citehop_s03_300 citehop_s03_200; do
  DB_NAME=$db python -m citehop.apply_sql sql/corpus_schema.sql
  DB_NAME=$db python -m citehop.corpus --snapshot data/wikipedia/full.json
done
python -m citehop.chunk_experiment embed    # each arm in its own process, from empty chunks
python -m citehop.chunk_experiment dev      # 3 rounds, arm order alternates per round
python -m citehop.chunk_experiment freeze   # comparison.json + decision.json
python -m citehop.chunk_experiment test     # one follow-up test run of the chosen arm
```

## Measured, 2026-11-01

All runs used the same machine and setup: Apple M6, 24 GB, CPU, MariaDB 11.8.9 in Docker, `mhnsw_ef_search` 20. The machine was not idle (other workspaces' containers were running). **All 30 question labels are `unreviewed`** (`final_claims_allowed: false`), so these are harness results, not final claims. The runs record `code.dirty: true`; they were made from this change before it was committed.

### Chunks and embedding effort (full corpus, from empty)

| | 300 / 50 | 200 / 50 | Δ |
|---|---|---|---|
| Chunks | 1,776 | 2,937 | +65% |
| Passage length (tokens) | 51–300 | 53–200 | |
| Max model input (with title, specials) | 310 | 210 | |
| Model input tokens embedded | 530,822 | 595,589 | +12% |
| Model time (`embed_seconds`) | 82.0 s | 86.0 s | +5% |
| Process wall time | 91.9 s | 92.8 s | |
| Peak RSS (`wait4`) | 1.50 GB | 1.42 GB | |
| `chunks` table (data + indexes, `information_schema`) | 20.0 MB | 32.4 MB | +62% |

Embedding effort grows much less than the chunk count. Total tokens rise only by the extra overlaps, and shorter sequences are cheaper per token. The extra cost is mainly in storage and the number of rows to scan.

### Dev Recall@5 (8 answerable questions; 2 unanswerable reported separately)

| Method | 300 / 50 | 200 / 50 |
|---|---|---|
| Vector (ANN) | **1.0** | **1.0** |
| Exact | 1.0 | 1.0 |
| Keyword | 0.833 (misses dev-05, dev-08) | 0.958 (misses dev-05) |

Recall was identical in all three rounds of each arm. ANN and exact agree completely in both arms: chunk overlap@5 is 1.0 on all 7 unfiltered questions. No answerable question had zero hits or a short list.

**Decision** (`decision.json`, frozen 2026-11-01T14:15:18Z): keep **300/50**. The vector difference is +0.0000. The keyword gain (+0.125, one question) cannot switch the choice under the rule.

The keyword difference is not robust evidence anyway. In the tracked C08/C14 runs, the identical 300/50 chunks (same chunk IDs) gave keyword dev recall 0.958, and dev-08 was a hit there. Here, InnoDB FULLTEXT returned different relevance scores for the same chunk: 3.19 here against 3.73 in C14 for the top dev-08 hit. That is enough to push the relevant article out of the top five. FULLTEXT relevance depends on the index's internal statistics, not only on the stored rows. Vector rankings were identical to C14 (top-10 chunk IDs equal on every dev question).

### Dev latency (ms; median / p95 over 3 runs; 30 samples, 21 unfiltered, 9 filtered)

| Boundary (as in [EVALUATION.md](EVALUATION.md)) | 300 / 50 | 200 / 50 |
|---|---|---|
| Query embedding | 36.0 / 43.3 | 36.0 / 39.6 |
| Keyword | 5.7 / 10.9 | 7.9 / 13.2 |
| Vector, unfiltered (HNSW) | 7.2 / 9.9 | 7.4 / 8.4 |
| Vector, filtered (exact scan) | 25.9 / 285.3 | 40.0 / 383.4 |
| Exact, unfiltered (full scan) | 167.8 / 194.1 | 271.8 / 297.3 |

- **Scans grow with the chunk count, HNSW does not.** Exact and filtered vector search scan every eligible row, so they are about 60% slower with 65% more rows. Indexed search barely changes at this size.
- **Small samples.** The p95 values are taken from 9 or 21 samples, so they are close to the maximum.
- **Query embedding.** The dev query-embedding times are higher than in C08. Each dev run is a fresh process with only one warm-up call. The times are the same for both arms.

### Labeled follow-up test run (after the freeze; confirmation only)

The run is labeled `S03 follow-up test of frozen choice 300-50 (decision.json sha256 012546eb…)`. Run `20261101T141540Z-test-75d4babd` used 300/50 in `citehop_s03_300`, with 3 repetitions and no generation (`followup.json`).

| Test split, 17 answerable | Recall@5 |
|---|---|
| Keyword | 0.959 |
| Vector | 0.976 |

This matches the tracked C08 test results (0.959 / 0.976). Latency, median / p95 ms: embedding 11.2 / 14.0 (n=54), keyword 5.0 / 5.8 (n=54), vector unfiltered 6.9 / 7.5 (n=38), vector filtered 31.8 / 76.4 (n=16). 200/50 was not run on test. Test numbers were not used for, and cannot change, the choice.

## Limits

- **Dev is small.** It has 8 answerable questions, and vector recall is already 1.0 at 300/50, so this dev set cannot show a vector gain for 200/50. A larger or harder dev set might.
- **Labels are unreviewed.** All conclusions are provisional until review.
- **Retrieval only.** Answer quality with 200-token passages (5 passages ≈ 1,000 tokens instead of ≈ 1,500 in the 1,800-token budget) was not measured.
