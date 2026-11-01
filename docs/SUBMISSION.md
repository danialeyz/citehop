# Course submission record (C14)

What was reproduced from a clean checkout, which checks ran, where each reported number comes from, and what is still open. Date: 2026-10-31. Machine: Apple M6, 24 GB, macOS 27.0, Docker Desktop; MariaDB 11.8.9 and Neo4j 5.26.32 Community in Docker, API and frontend on the host.

## Clean reproduction

The checkout started with no `.env`, `.venv`, `node_modules`, `data/` cache or database volumes. A separate Compose project (`COMPOSE_PROJECT_NAME=citehop-spokane-c14`, MariaDB on 3317, Neo4j Bolt on 7697) was used, so the existing `citehop-maputo` volumes were not touched. Every step below is a README command.

| Step | Command | Result | Wall time |
|---|---|---|---|
| Environment | `cp .env.example .env` (ports/passwords edited), `cp frontend/.env.example frontend/.env.local` | — | — |
| Dependencies | `make venv-ml frontend-install` | locked installs | ~1 s / 5 s (warm uv/npm caches) |
| Databases | `make db-up && make check` | both healthy, cosine check 0.0 | 13.5 s |
| Wikipedia fetch | `python -m citehop.acquire fetch --subset full` | **first attempt failed** (see below); after the fix 100/100 records, `full.json` byte-identical to an earlier cache (SHA-256 `202568aa…`) | 3 min 13 s for 99 downloads |
| Schema + load | `make sql FILE=sql/corpus_schema.sql`, `python -m citehop.corpus --snapshot data/wikipedia/full.json` | 100 articles, 456 categories, 917 links, content SHA-256 `d491fa4b…` | 0.3 s + 0.2 s |
| Embeddings | `make embed` | 100 articles, 1,776 chunks, embedding config `35e53e16…` (same as the C05–C08 runs) | 148.7 s, peak RSS 1.53 GB |
| Graph | `make graph-import && make graph-status` | `ready`, 100 / 456 / 917 / 1,101, version `corpus:1` | 2.0 s |
| RAG | `scripts/validate_rag.py --out .context/…` | grounded case answered with `[S1]`, unanswerable `insufficient_evidence`, injected instruction ignored | 14.8 s |
| Evaluation | `make eval` | run `20261031T174404Z-dev-test-15b1f5a1` (tracked) | 33 s |
| API | `make api`, `scripts/smoke_api.py http://127.0.0.1:3010` | every route 200, one real answer | — |
| Views | `npm run build && npm start`, `npm run e2e` | journey passed (below) | — |

**Fetch failure found and fixed.** MediaWiki re-parsed the pinned revision of *Natural language processing* when its parser cache expired. The response differed only in an HTML comment (parser host, cache time, CPU timings), but the raw-response hash no longer matched the pin, so a clean fetch stopped. `citehop/acquire.py` now accepts such a re-render only when the extracted record (text, categories, links, URLs) is identical to the pinned record; it keeps the pinned raw hash and lists the title under `rerendered` in the fetch report. Any content change is still rejected (`tests/test_acquire.py`).

**Version labels are per database.** A fresh full load is `corpus:1`; the earlier development database loaded the smoke subset first, so the same content is `corpus:2` there. Both runs record the same `content_sha256` (`d491fa4b…`), which is the identity to compare.

## Checks

| Check | Command | Result |
|---|---|---|
| Backend unit tests | `make test` | 177 passed |
| Python lint | `make lint` | clean |
| MariaDB integration | `CITEHOP_TEST_DB_NAME=citehop_test pytest -m db` (disposable DB on the isolated server) | 21 passed |
| Neo4j integration | `make test-graph` against a throwaway container | 11 passed |
| Model | `make test-model` | 3 passed |
| Frontend | `make frontend-check` (lint, typecheck, 21 node tests, production build) | pass |
| Browser journey | `make e2e` / `npm --prefix frontend run e2e` (`frontend/e2e/journey.mjs`, Playwright 1.64.1, headless Chromium) | 17 checks passed, first on the C10–C13 UI, then again on 2026-11-01 after rebasing onto master `b988bbd` (#17 charcoal/lime redesign, #18–#19 README); the tracked screenshots are from that second run |
| Neo4j outage | stop the isolated Neo4j container, call the API | `/search` 200, Library and Dashboard 200, `/graph/status` `unavailable`, `/graph/neighborhood` 503 `graph_unavailable`; status `ready` again after restart |
| SQL plans | `make sql FILE=sql/search_examples.sql` | example 1 `ft_chunks_text`, example 2 `vx_chunks_embedding`, example 3 exact scan via `uq_chunks_position`, as in RETRIEVAL.md |

The search box is located by its stable `id` inside the search landmark (`getByRole("search").locator("#q")`), not its visible label, which #17 changed. The browser journey, on real data: search (5 sources, no generator call) → **Generate answer** (exactly one `/answer` call, *Answered with citations*) → open citation S1 and compare it with the stored chunk from `/articles/{id}` (identical) → **Explore connections** (graph keeps the search context; 55 nodes) → select and expand a neighbor (55 → 63 nodes, seed position unchanged) → path from the seed to an article 2 links away (2 edges highlighted) → Dashboard (no generation call) → Library → all four routes at 390 px without horizontal overflow, and no page errors.

Stale-graph refusal and graph timeouts were not forced on this stack; they are covered by `make test-graph` (stale version refuses queries) and the API tests (409/504 bodies). C04 measured a real stale-and-reimport cycle ([GRAPH.md](GRAPH.md)).

## Where the numbers come from

| Reported figure | Source |
|---|---|
| Recall@5, latency, generation timings, review counts | `results/runs/<run_id>/manifest.json` (`summary`); per-question rows in `retrieval.jsonl`, answers in `answers.json` |
| Corpus, chunk and graph counts | live `GET /api/v1/stats`, `make embed-status`, `make graph-status`; [DATA_MODEL.md](DATA_MODEL.md), [GRAPH.md](GRAPH.md) |
| Embedding settings and limits | `embedding_configs` table; [EMBEDDINGS.md](EMBEDDINGS.md) |
| ANN vs exact plans and fixture recall | [RETRIEVAL.md](RETRIEVAL.md), `sql/search_examples.sql`, `scripts/search_fixture.py` |
| Graph render timings | [GRAPH_EXPLORER.md](GRAPH_EXPLORER.md) (C12 measurement) |
| Memory and disk below | `docker stats --no-stream`, `docker system df -v`, `ps` RSS, `/usr/bin/time -l`, on this machine after the journey |

Both tracked runs use config `15b1f5a1…` on identical content. Recall is identical in both. Latencies are higher in the C14 run, which ran while the embedding job, API and browser shared the machine; treat the two as a spread on one laptop, not as a benchmark.

| Test split (20 questions, 3 repetitions) | Run 162301Z (C08) median / p95 ms | Run 174404Z (C14) median / p95 ms |
|---|---|---|
| query embedding (n=54) | 12.9 / 18.6 | 15.3 / 30.5 |
| keyword (n=54) | 5.6 / 9.5 | 7.8 / 17.4 |
| vector, unfiltered, HNSW (n=38) | 7.7 / 14.7 | 10.3 / 22.2 |
| vector, filtered, exact scan (n=16) | 37.4 / 90.3 | 42.2 / 82.8 |
| dev exact, unfiltered (n=7) | 184.8 / 265.5 | 218.6 / 303.9 |
| generation (n=10) | 2,033 / 2,338 | 2,171 / 2,665 |

## Cost of the second database

Measured on the isolated stack after the import and the browser journey:

| | MariaDB | Neo4j |
|---|---|---|
| Container memory | 133 MiB after load, 184 MiB after the journey | 583 MiB after import, 727 MiB after the journey (heap capped at 512 MB, page cache 256 MB in Compose) |
| Data volume | 234 MB (text, chunks, vectors, indexes) | 541 MB (100 + 456 nodes, 2,018 edges, plus store files and transaction logs) |
| Extra steps | — | `make graph-import` after every corpus change (2.0 s here), one more service, password and port |

Other processes: the API with the BGE model loaded about 0.25 GB RSS, `next start` about 27 MB, the embedding job 1.5 GB peak, and Ollama's 14 GB generator model.

## Snapshot consistency limitations

- The graph is a copy. There is no cross-database transaction, no background sync and no request-time dual write. Between a MariaDB load and `make graph-import`, Neo4j is behind.
- Staleness is detected by comparing `corpus_versions.version_id` with the version stored at import. The API caches that lookup for 5 s, so a change can take up to 5 s to show as `stale`. While stale, traversal is refused; search, Library and Dashboard keep working.
- Rebuilds are in place: while `rebuilding`, there is no current graph, and a failed import stays `rebuilding` until a later import succeeds. The previous snapshot is not kept.
- Versions are counters in one database (see *Version labels* above); compare `content_sha256` across machines.
- A link in the graph is a Wikipedia hyperlink in the pinned revision, not a citation or agreement. Hidden maintenance categories are stored as ordinary categories; the explorer filters them by name pattern.

## Assignment checklist ([area 4](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively))

| Requirement | Status |
|---|---|
| README first line names the area and links the page | done |
| Public GitHub repository, code on the `main` branch, README at the root | **open**: `danialeyz/citehop` is public, but its default branch is `master`. The evaluation prompt reads `main` and stops if it is empty. Before submitting, the team must create or rename `main` with this code (not done here: no branch renames or publishing). |
| MariaDB throughout, version stated | 11.8.9 (Docker image `mariadb:11.8.9`) |
| Data in the repo or fetched by a documented, repeatable step | pinned manifest `eval/corpus.json` + `python -m citehop.acquire fetch`; verified from scratch |
| `VECTOR` column with an index over a real Wikipedia corpus, queried with `VEC_DISTANCE_COSINE` | `chunks.embedding VECTOR(768)`, `VECTOR INDEX … M=16 DISTANCE=cosine` |
| Semantic search and SQL predicates in the same statement, joined back | category, article length and linked-from predicates (`EXISTS`) in the ranked statement; metadata join on `(article_id, revision_id)` |
| "Edited since that date" example from the brief | **not implemented** as a filter; `revision_timestamp` is stored, so it would be one more predicate |
| Recall and latency against a ground-truth set you built | 30 questions, Recall@5 and median/p95; **labels not yet human-reviewed** (`final_claims_allowed: false`) |
| Chunk size, embedding model, index parameters with reasoning | README *Design decisions* |
| Ingest runs from the README; a query interface a reader can try | README *Run it*; web UI, CLI (`python -m citehop.search`) and SQL examples |
| What the database-native approach gave us | README section of that name |
| Schema with reasoning, architecture, screenshots, team | README, [DATA_MODEL.md](DATA_MODEL.md), [ARCHITECTURE.md](ARCHITECTURE.md), `docs/screenshots/` |

## Blocked or not done

- **Human review.** All 30 question labels and all 10 saved answers are unreviewed. A team member other than the author must review them ([eval/README.md](../eval/README.md), [EVALUATION.md](EVALUATION.md)). Until then every metric is provisional, and the grounding result is "Not reviewed".
- **`main` branch.** See the checklist; a repository-owner action.
- **Prerequisites not installable from the README alone.** Ollama and its 14 GB model, Docker, and the native Connector/C. `make venv` needs `mariadb_config` on `PATH` (Homebrew's `mariadb-connector-c` is keg-only). The e2e test needs `npx playwright install chromium` once.
- **Not measured.** Large-corpus behavior, concurrent users, and frame rates beyond the C12 observations. A 100-article corpus validates the method; it does not establish performance at scale.
