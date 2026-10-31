# CiteHop HTTP API (C09)

FastAPI app: `citehop/api/main.py` (routes) and `citehop/api/schemas.py` (Pydantic models). The OpenAPI document is the contract: `http://127.0.0.1:8000/docs`, or `frontend/lib/api/openapi.json` in the repository. Routes are thin and reuse `citehop.search`, `citehop.rag`, `citehop.graph.queries`, `citehop.library` (article/passage SQL), and `citehop.runs` (saved runs).

| Route | Notes |
|---|---|
| `GET /api/v1/health` | Always 200 while the API runs; `services.mariadb` / `services.neo4j` are `ready` or `unavailable`. |
| `POST /api/v1/search` | `query`, `method` (`keyword`/`vector`/`exact`), `filters` (`category`, `min_length_chars`, `max_length_chars`, `linked_from`), `k` 1–100. Unknown fields are rejected. Returns hits, effective filters, `corpus_version`, `embedding_config`, and separate `embedding_ms` / `retrieval_ms` / `total_ms`. Never touches Neo4j. |
| `POST /api/v1/answer` | `question`, 1–5 `chunk_ids` (64-hex), and the `corpus_version` from the search response. The server reads passage text from MariaDB; clients cannot send passages. |
| `GET /api/v1/articles` | `title` (case-insensitive substring), `category` (exact), `page`, `page_size` ≤ 100. Ordered by title. |
| `GET /api/v1/articles/{id}` | Metadata, license/attribution, categories, link counts, and a page of stored passages (`passage_page`, `passage_page_size` ≤ 50) from the newest embedding configuration. |
| `GET /api/v1/graph/status` | Always 200; `status` is `ready`, `stale`, `rebuilding`, or `unavailable`, with source and imported versions. |
| `GET /api/v1/graph/neighborhood` | `article_id`, `hops` 1–2, `max_nodes` ≤ 100 (default 50), `max_edges` ≤ 200 (default 100), repeated `rel_types`. Returns `truncated`, `graph_version`, `seed`, `limits`. |
| `GET /api/v1/graph/path` | `source_id`, `target_id`, `directed` (default true). `found: false` comes with "No path within 3 links". |
| `GET /api/v1/stats` | Live MariaDB counts and chunk coverage per embedding configuration; graph status as a separate block. |
| `GET /api/v1/runs`, `/runs/{id}`, `/runs/{id}/export` | Saved evaluation runs (layout below). CSV has fixed columns. |

## Errors

Request-schema violations return FastAPI's 422 `detail` list. Every other error returns `{"error", "message"}` plus optional `current_corpus_version`, `missing_chunk_ids`, or `graph` (sanitized status). Messages are fixed strings; exception text, hosts, credentials, and file paths are only logged.

| HTTP | `error` | Meaning |
|---|---|---|
| 404 | `not_found`, `unknown_chunks`, `run_not_found` | Missing article, chunk IDs not in the current corpus, or no such run. |
| 409 | `stale_context` | The `corpus_version` sent with `/answer` is not current; search again. |
| 409 | `graph_stale`, `graph_rebuilding` | Traversal is disabled until the graph matches MariaDB (`make graph-import`). |
| 409 | `embedding_mismatch` | The stored chunks do not match the query embedder's configuration. |
| 422 | `invalid_request` | Semantically invalid input, such as `min_length_chars` > `max_length_chars`. |
| 429 | `generation_busy` | One answer is already being generated. Not queued or retried. |
| 500 | `malformed_run`, `internal_error` | Unreadable saved run, or an unexpected server error. |
| 503 | `mariadb_unavailable`, `graph_unavailable`, `embedder_unavailable` | Service down, graph never imported, or the ml extra is missing. |
| 504 | `graph_timeout` | A graph query exceeded its transaction timeout. |

`/answer` returns 200 for every generation outcome. Check `status`: `answered`, `insufficient_evidence`, `invalid_citations`, or `provider_error`. With `provider_error`, the resolved sources are still returned and `reason` is a fixed message.

## Concurrency

All handlers are synchronous `def`s, so FastAPI runs the blocking MariaDB, Neo4j, embedding, and Ollama calls in its thread pool, off the event loop. Query embedding is serialized by a lock, which also guards the lazy model load. One generation runs per process; a concurrent `/answer` gets an immediate 429. The MariaDB connection is closed before the generation call starts. Run one API worker (`make api`) so the embedding model is loaded only once.

## Saved runs

The API reads the C08 run layout ([EVALUATION.md](EVALUATION.md)) through `citehop/runs.py`. It accepts only manifests with schema `citehop-eval-v1` (shared with `citehop.evaluate.SCHEMA`) whose `run_id` matches the directory name. Each run also needs `created_at`, `splits`, and `corpus.id`. The `retrieval` and `answers` names in `files` must be plain file names inside the run directory. `CITEHOP_RUNS_DIR` overrides `results/runs`.

- `GET /runs` lists the manifests, newest first, unchanged (config, latency boundaries, hardware, warm-up, and `summary` with denominators; nulls stay null). Unreadable runs appear under `invalid` and are not dropped silently.
- `GET /runs/{id}` returns the manifest, `rows`, `answers`, and `counts`. There is one row per question repetition and method; the answer prepared for review joins on question, method, and repetition. Answers include review fields and source IDs/titles, but no passage text or raw model output.
- `GET /runs/{id}/export` returns the same rows as CSV with fixed columns: `question_id, split, repetition, method, answerable, filtered, recall_at_5, articles_found, exhausted, cutoff_reached, top_article_ids, embedding_ms, retrieval_ms, answer_status, generation_ms, review_status`. `top_article_ids` holds the first five distinct articles, separated by `;`. `embedding_ms` is empty for keyword rows, because keyword search embeds nothing. Missing values are empty cells, never 0. Text starting with `= + - @` is prefixed with `'`.

## Frontend client

`frontend/lib/api/client.ts` is the only client. It wraps [openapi-fetch](https://openapi-ts.dev/openapi-fetch/) with types that [openapi-typescript](https://openapi-ts.dev/) generates from `openapi.json` into `schema.d.ts`. In the browser it calls the same-origin `/api/*` Next proxy; in server code it calls `API_UPSTREAM`. After any schema change, run `make api-types`. `tests/test_api.py` fails while `openapi.json` is out of date.

## Smoke check

```bash
make graph-import                      # once per corpus version
make api                               # terminal 1
make frontend                          # terminal 2
.venv/bin/python scripts/smoke_api.py  # via the Next proxy on :3000; one real generator call
```

`results/c09_api_smoke.json` records the C09 run against `corpus:2`.
