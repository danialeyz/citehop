# Migration audit (M0)

Status: draft for human review. No code was changed. M0 adds this file and its companion, [MIGRATION_PROMPTS.md](MIGRATION_PROMPTS.md) (agent prompts for M1 to M8, written on request after the audit).

Source: `MIGRATION_HANDOFF.md` (pasted into the session on 2026-11-01). Baseline: commit `7be64f1` on `master`.

Baseline health at audit time:
- `pytest -m 'not db and not neo4j and not model'`: 213 passed, 1 skipped, 40 deselected.
- `make lint`: all checks passed.
- DB, Neo4j and model tests were not run in M0 (they need running services).

## Blockers before M1

1. **`CITEHOP_BOOTSTRAP.md` is not in the repo.** The handoff says it holds the exact schema, Makefile, Docker, CI and test files (sections 4.9, 4.10, 4.21). M1 and M2 copy from it. Please add it to the repo root.
2. **`MIGRATION_HANDOFF.md` is not in the repo either.** It was pasted, not committed. Recommend committing it next to the bootstrap so later phases can cite it.
3. **Branch and PR target.** The handoff asks for a `migrate/citehop` branch with one PR per phase into it. This workspace is on `danialeyz/pasted-text`, and no `migrate/citehop` branch exists. Decide: create `migrate/citehop` from `master` as the integration branch, or PR each phase straight into `master`.

## 3.1 What exists

The prototype is not a toy. It is a finished course project (cards C01 to C14, S01 to S03) with a different scope: RAG over 100 Wikipedia articles, with a Neo4j graph.

| Area | Prototype | Files |
|---|---|---|
| Language and framework | Python 3.11 (uv, setuptools), FastAPI; Next.js 16 / React 19 / TypeScript / Tailwind 4 frontend | `pyproject.toml`, `.python-version`, `citehop/api/main.py`, `frontend/package.json` |
| Database engine | MariaDB `11.8.9` (pinned) in Docker Compose. Second engine: Neo4j `5.26.32-community` | `docker/docker-compose.yml` |
| Vector store | In MariaDB. `chunks.embedding VECTOR(768) NOT NULL`, `VECTOR INDEX ... M=16 DISTANCE=cosine` inside the schema file | `sql/corpus_schema.sql:65-82` |
| Corpus and size | 100 English Wikipedia ML articles, revision-pinned, 10-article smoke subset. 1,776 chunks at 300/50 tokens. CC BY-SA | `eval/article_titles.txt`, `eval/corpus.json`, `citehop/acquire.py`, `citehop/corpus.py` |
| Embedding model | `BAAI/bge-base-en-v1.5`, revision `a5beb1e3...`, 768 dims, CLS pooling, L2 norm, CPU, local | `citehop/embed.py:29-60`, `docs/EMBEDDINGS.md` |
| Search modes | `keyword` (FULLTEXT natural language), `vector` (HNSW), `exact` (no index), `hybrid` (RRF k=60 over top 50 + top 50, in Python). SQL filters: category, length, linked-from. All over chunks, not papers | `citehop/search.py`, `docs/RETRIEVAL.md` |
| Graph data | Wikipedia internal links and categories in MariaDB (`article_links`, `article_categories`), projected into Neo4j (`Article`, `Category`, `LINKS_TO`, `IN_CATEGORY`). No citations, authors or concepts. S02: 1-hop Neo4j expansion rerank experiment | `citehop/graph/`, `citehop/graph_retrieval.py`, `docs/GRAPH.md`, `docs/GRAPH_RETRIEVAL.md` |
| Evaluation | 30 AI-drafted questions (10 dev, 20 test), all `unreviewed`. Article-level Recall@5 only. ANN vs exact overlap. Latency p50/p95. Saved run manifests with git state and hardware. S03 chunk-size experiment decided on dev only | `eval/questions.json`, `citehop/evaluate.py`, `citehop/chunk_experiment.py`, `results/` |
| RAG | Cited answers from a local Ollama model, at most 5 passages | `citehop/rag.py`, `docs/RAG.md` |
| UI | Next.js pages: Search (with cited answer), Library, Graph (React Flow explorer on Neo4j), Dashboard (Recharts) | `frontend/app/`, `frontend/components/`, `docs/GRAPH_EXPLORER.md`, `docs/screenshots/` |
| API | FastAPI under `/api/v1`: `health`, `search`, `answer`, `articles`, `articles/{id}`, `graph/status`, `graph/neighborhood`, `graph/path`, `stats`, `runs`, `runs/{id}`, `runs/{id}/export`. Typed OpenAPI client for the frontend | `citehop/api/main.py`, `citehop/api/schemas.py`, `docs/API.md` |
| Tests | 16 test files plus the helper `tests/corpus_fixtures.py`, markers `db`, `neo4j`, `model`. API tests use fakes for DB, model and generator. Frontend unit tests (`node --test`) and a Playwright journey | `tests/`, `frontend/lib/`, `frontend/e2e/journey.mjs` |
| CI | None. No `.github/` directory | (missing) |
| Deployment | Local only. Compose runs the two databases. API and frontend run on the host. No prod containers, Caddy, backups or release pipeline | `docker/docker-compose.yml`, `Makefile` |

## 3.2 Gap table

Effort: S under 2 h, M half a day, L a day or more.

### Platform

| # | Capability | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| P1 | Docker `mariadb:11.8.9` + `my.cnf` (`mhnsw_max_cache_size=1G`, `innodb_ft_min_token_size=2`) | Partial | `docker/docker-compose.yml` pins 11.8.9; no `my.cnf` | Add `docker/my.cnf` and mount it. Recreate the volume or rebuild FULLTEXT indexes after the token size change | S | #2 |
| P2 | `citehop/` package, Makefile, `.env`, ruff, pytest (unit + `db`) | Done | `citehop/`, `Makefile`, `.env.example`, `pyproject.toml` | Add bootstrap targets (`schema`, `kg-schema`, `test-db`, `inspect`) next to the existing ones. Keep `uv` locks | S | #6 |
| P3 | CI with a MariaDB 11.8.9 service, schema applied twice, db tests | Missing | none | Add workflow from bootstrap 4.21. Add frontend lint/typecheck/build as a second job | M | #6 |
| P4 | `CLAUDE.md`, `README.md`, `docs/` (ARCHITECTURE, DATA_MODEL, DECISIONS, EXPERIMENTS, RESULTS, TRAPS, GLOSSARY, CONTRIBUTING) | Partial | README, ARCHITECTURE, DATA_MODEL exist but describe Wikipedia + Neo4j. `app/CLAUDE.md` and `frontend/AGENTS.md` exist, no root `CLAUDE.md`. Em dashes in README, COURSE_TASKS, GRAPH, SUBMISSION, AGENT_PROMPTS, design docs | Add root `CLAUDE.md` and the six missing docs. Rewrite ARCHITECTURE and DATA_MODEL per phase. Remove em dashes as files are touched | M | #6, #31 |

### Data model

| # | Capability | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| D1 | `papers` with FULLTEXT | Missing | `articles` is the nearest match (Wikipedia page, full text, no abstract/year/venue) | New table from bootstrap. `articles` stays until M8 | S | #8 |
| D2 | `citations` with reverse key | Conflicts | `article_links` has the same shape (PK + reverse key) but holds Wikipedia links, not citations | New table. Reuse the key pattern and the self-link `CHECK` | S | #8 |
| D3 | `emb_bge_base (corpusid PK, emb VECTOR(768) NOT NULL)` | Conflicts | Vectors live on `chunks`, one row per chunk, many models mixed by `embedding_config` hash. Index is in the schema file (breaks rule 10) | New per-paper table, no index in DDL. Index added after load (M3) | S | #8, #15 |
| D4 | `queries`, `qrels` with kind, origin, split | Missing | Questions live in `eval/questions.json`, not in the DB | New tables, loaded from LitSearch | S | #8, #12 |
| D5 | `runs` with `found_via SET(...)` | Missing | Runs are JSON files in `results/runs/`. Hits carry one `method` string | New table. JSON manifests can still be written next to it | S | #8, #19 |
| D6 | `authors`, `paper_authors`, `venues` | Missing | none | New tables | S | #12.5 |
| D7 | `concepts`, `concept_aliases`, `paper_concepts` | Missing | none. Prototype scope explicitly said "no LLM entity extraction" (`docs/COURSE_TASKS.md`) | New tables in `sql/kg_schema.sql` | S | #12.5 |
| D8 | view `kg_links (a, b, rel)` | Missing | Neo4j plays this role today | New view | S | #12.5 |
| D9 | `search_log` (hash only) | Missing | none | New table | S | #34 |

No target table name collides with a prototype table (`corpus_versions`, `articles`, `article_categories`, `article_links`, `chunks`, `embedding_configs`). M2 needs no `proto_` renames.

### Data pipeline

| # | Step | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| L1 | Download LitSearch, `data/NOTES.md` | Missing | `citehop/acquire.py` downloads Wikipedia. `.gitignore` already allows `data/NOTES.md` | New `make inspect` and NOTES. Reuse the pin-and-verify cache pattern from `acquire.py` | S | #9 |
| L2 | Load papers, in-corpus citations, `n_cited_by` | Missing | `citehop/corpus.py` batch loader with versioning | New `load_corpus.py`. Reuse the batch insert and count checks | M | #10 |
| L3 | Questions, qrels, stratified 20/80 split, seed 42 | Conflicts | 30 questions, fixed 10/20 split, hand-drafted | New `load_questions.py`. Old questions become a demo extra or are retired (see 3.3) | S | #12 |
| L4 | Embed on Colab, check, bulk load, then cosine index | Partial | `citehop/embed.py` embeds locally on CPU with a pinned revision and resumable writes. No Colab notebook (`notebooks/` is empty). No `.npy` pair. Index is pre-created | Colab notebook writing `.npy` ids + vectors with the same model revision. `load_vectors.py` binds bytes, then `ALTER TABLE ... ADD VECTOR INDEX`. Reuse `Embedder` for query embedding | M | #13, #14, #15 |
| L5 | Authors, venues, years from Semantic Scholar | Missing | none | New script. Needs `S2_API_KEY` | M | #12.7 |
| L6 | 50-abstract gold set, LLM extraction, quote check, concept merge | Missing | none. `citehop/rag.py` has a reusable pattern for untrusted text and label checking | New pipeline. Human gold labels. Paid LLM cost needs approval | L | #13.5, #14.5, #15.5 |

### Search pipeline

| # | Step | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| S1 | Keyword `MATCH ... AGAINST` natural language, top 100 | Partial | `citehop/search.py:160-164`, over `chunks.text`, max k 100 | Same SQL against `papers` (title + abstract). Move to `sql/` | S | #16 |
| S2 | Exact vector shape, top 100, EXPLAIN proves index | Partial | `citehop/search.py:166-171`. Shape is right when unfiltered. Vectors bound as JSON text via `VEC_FromText(?)`, not bytes (rule 11). EXPLAIN test in `tests/test_corpus_db.py` | Bind `<f4` bytes after length check. Query `emb_bge_base`. Keep the EXPLAIN test pattern | S | #17 |
| S3 | RRF in SQL (`UNION ALL` + `GROUP BY`), top 10 seeds | Conflicts | S01 RRF is computed in Python (`rrf` in `citehop/search.py:72`) | Rewrite as SQL. Keep the Python version as the reference in tests | M | #18 |
| S4 | Citation expansion, recursive CTE, both directions, 1 to 2 hops, weighted, halved per hop, `/ LOG(2 + n_cited_by)` | Conflicts | S02 does 1 hop in Neo4j over Wikipedia links, then reranks in MariaDB (`citehop/graph_retrieval.py`) | New CTE in `sql/`. S02's bounded, fail-safe design (fall back to seeds) is worth keeping | M | #22 |
| S5 | Shared references, cited-together self-joins | Missing | none | New SQL | S | #23 |
| S6 | Concept (K, IDF) and author (L) expansion | Missing | none | New SQL after M6 | M | #23.5, #23.6 |
| S7 | Rerank `a*meaning + b*graph + c*popularity (+ ...)`, each 0 to 1 | Partial | S02 uses `cosine + 0.1 * support / seeds`, a fixed untuned weight | New weighted rerank. Port S02 support as one graph term | M | #24 |

### Evaluation

| # | Capability | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| E1 | `evaluate.py` fills `runs`, Recall@5, Recall@20, nDCG@10, MRR, SQL and Python agree | Partial | `citehop/evaluate.py` has article-level Recall@5, latency, manifests, hand-scored metric tests | Add Recall@20, nDCG@10, MRR in `metrics.py` and `sql/grade.sql`. Write to `runs`. Keep manifests | M | #19 |
| E2 | SciFact sanity check, nDCG@10 near 74.04 | Missing | none | New script. Downloads and embeds SciFact (about 5k docs, CPU is fine) | M | #20 |
| E3 | Index sweep, exact vs HNSW over ef_search and M, recall at least 0.95 | Partial | `ann_vs_exact` in `citehop/evaluate.py` compares at one setting (M=16, ef 20) on 100 articles | Sweep on LitSearch. Record choice in DECISIONS | M | #21 |
| E4 | Weight tuning on dev only | Partial | S03 shows the discipline (freeze rule, test locked until decision) | Reuse the freeze-then-test guard for weights | S | #25 |
| E5 | Configs A to L on test, paired bootstrap vs C | Missing | none | New | M | #26 |
| E6 | Latency p50 and p95 per config | Done (pattern) | `latency()` in `citehop/evaluate.py`, warm-up policy and timing boundaries recorded | Run per config | S | #27 |

### Product and production

| # | Capability | Status | Where in the prototype | What has to change | Effort | Cards |
|---|---|---|---|---|---|---|
| U1 | Search page shows `found_via` and citation path | Partial | `frontend/components/search/` shows method, ranks and cited passages | Add `found_via` tags and the citation path. Paper cards instead of passage cards | M | #28 |
| U2 | Graph Explorer on real data (2-hop, node cap, path view, SQL panel) | Partial | `frontend/components/graph/` has 2-hop, caps, truncation and path view, fed by Neo4j | Feed it from SQL over `kg_links`. Add SQL panel. Node types: paper, author, concept, venue | M | #28.5 |
| A1 | FastAPI `/health`, `/search`, `/paper/{id}`, `/graph/{id}`, validated inputs, fake embed backend | Partial | `citehop/api/main.py` under `/api/v1` with Pydantic validation and fakes in tests | Add `/paper/{id}`, `/graph/{id}`. Make the fake embedder selectable by env for CI | M | #32 |
| A2 | Read-only DB user, connection pool, `max_statement_time` | Missing | `citehop/db.py` opens one connection per request as the owner user | Add pool, read-only user, statement timeout | S | #33 |
| A3 | `search_log` + JSON logs | Missing | none | New | S | #34 |
| O1 | Prod containers (db, api, app, caddy), model baked in, non-root | Missing | none | New | L | #35 |
| O2 | Snapshot, nightly backup, restore drill | Missing | `scripts/check_persistence.py` checks volume survival only | New | M | #36 |
| O3 | Load test and budget | Missing | none | New | M | #37 |
| O4 | Security checklist and CI checks | Partial | Good habits: no SQL/Cypher in browser, secrets server-side, escaped model output | Write checklist, add CI checks | S | #38 |
| O5 | HTTPS deploy, release with rollback, uptime check, runbook | Missing | none | Scripts and RUNBOOK only. Deploy is a human task | M | #39 to #42 |

### Target rules the prototype breaks today

| Rule | Where | Note |
|---|---|---|
| 10. Vector index after bulk load, never in a schema file | `sql/corpus_schema.sql:77` | Leave the legacy file alone. New schema follows the rule |
| 11. Bind vectors as `<f4` bytes | `citehop/search.py:167` (`VEC_FromText(?)`) and `:219-225` (`vector_text()`), `citehop/embed.py:145`, `citehop/graph_retrieval.py:189` | Uses JSON text and `VEC_FromText`. Length and finite checks already exist |
| 15. No SQL built with f-strings | `citehop/search.py:134,168,174-181`, `citehop/library.py:39-40,54,60,115,117-118,146`, `citehop/corpus.py:135,147,157-160,215`, `citehop/graph_retrieval.py:190-194` | Values are bound as parameters, but clause text is composed with f-strings. New code keeps SQL in `sql/` files |
| 16. No em dashes in docs | see P4 | Fix as each doc is rewritten |

## 3.3 Conflicts that need a human decision

1. **Corpus: Wikipedia (100 articles) vs LitSearch (64,183 papers).**
   Recommend: switch to LitSearch for all graded work, and keep the Wikipedia loader only as an optional demo behind a flag until M8. LitSearch has 597 labelled questions and real citations; the prototype has 30 unreviewed questions, so no prototype number can be a final claim.

2. **Second database: Neo4j vs recursive CTEs in MariaDB.**
   Recommend: move graph walks and the Explorer to SQL over `kg_links`, keep Neo4j running side by side until the SQL Explorer passes its tests (M8), then delete it in its own commit. The target and the definition of done say one engine, and the prototype docs already flag a second database as a course risk (`docs/COURSE_TASKS.md`).

3. **Unit of retrieval: chunks vs whole papers.**
   Recommend: one vector per paper (title + abstract) in `emb_bge_base`, and drop chunking for LitSearch. Abstracts fit in 512 tokens and qrels label papers. S03 is not evidence here: dev vector Recall@5 was 1.0 at both chunk sizes, so it could not show a difference, and it never compared chunks with whole papers.

4. **Embedding model.** Same model (`BAAI/bge-base-en-v1.5`). No conflict. Recommend pinning the same Hugging Face revision in the Colab notebook so query and corpus vectors match.

5. **Where embeddings are computed: local CPU vs Colab.**
   Recommend: Colab for the 64,183 abstracts (human runs it), local `Embedder` for queries only. CPU for 64k passages is slow but free, so this is a choice, not a cost issue; Colab free tier needs no approval unless a paid GPU is used.

6. **RRF in Python vs SQL.**
   Recommend: SQL as the product path, Python `rrf` kept only as a test oracle. The SQL is the deliverable.

7. **RAG answer generation (Ollama).**
   Recommend: keep it as an optional mode in the API and UI, not graded (section 5). LitSearch labels papers, not answers.

8. **UI framework: Next.js vs Streamlit.**
   Recommend: keep Next.js, pointed at FastAPI as today. It already exceeds the target UI and is fully typed against OpenAPI.

9. **API path prefix: `/api/v1/...` vs `/search`, `/paper/{id}`, `/graph/{id}`.**
   Recommend: keep the `/api/v1` prefix and add the target routes under it. The frontend proxy and generated types depend on it.

10. **Prototype questions and results.**
    Recommend: keep `eval/questions.json` and `results/` in git as history, out of the graded tables. Config P is defined in decision 11.

11. **What "config P" means.** The prototype search runs over Wikipedia chunks, so it cannot be graded on LitSearch as is.
    Recommend: P = the prototype S01 recipe (FULLTEXT top 50 + HNSW top 50, Python RRF k=60, no graph) run over the new `papers` and `emb_bge_base` tables. It is the honest "before" number for the same data.

12. **Scope change itself.** The prototype was built for the MariaDB hackathon brief "Vector search and RAG natively" (`docs/COURSE_TASKS.md`). The target is a paper search engine with a knowledge graph and production deploy. Please confirm the target replaces the current course submission (`docs/SUBMISSION.md`), and is not a second deliverable.

## 3.4 Keep list

- **Next.js frontend and design system** (`frontend/`, `docs/design/`). Better than a Streamlit page. Search, Library, Graph and Dashboard views, loading/empty/error states, 1440 and 390 px checks.
- **Graph Explorer UI** (`frontend/components/graph/`, `frontend/lib/graph/model.ts`). Caps, truncation, deterministic layout and path view already exist. Only the data source changes.
- **FastAPI app** (`citehop/api/`). Pydantic validation, safe error bodies, OpenAPI-generated frontend types, fakes for every backend in `tests/test_api.py`.
- **Pinned embedder** (`citehop/embed.py`). Exact model revision, no silent truncation, config hash. Reuse for query embedding.
- **SQL runner and checks** (`citehop/apply_sql.py`, `citehop/check.py`, `citehop/db.py`). Rule 2 step 2 already holds: other code calls `citehop.db.connect()`.
- **Evaluation discipline** (`citehop/evaluate.py`, `citehop/chunk_experiment.py`). Run manifests with git commit, dirty flag, hardware, warm-up policy and timing boundaries. Freeze-on-dev, lock-test guards.
- **Hand-scored metric tests** (`tests/test_evaluate.py`). Pattern for E1 tests.
- **MariaDB HNSW trap** (`docs/RETRIEVAL.md:33`). A `WHERE` on an indexed vector query filters a bounded candidate list and can return fewer than k rows. Move into `docs/TRAPS.md`.
- **Pin-and-verify download cache** (`citehop/acquire.py`). Pattern for the LitSearch download.
- **Prompt-injection handling for untrusted text** (`citehop/rag.py`). Pattern for L6 concept extraction.
- **Makefile help, `uv` lockfiles, `.editorconfig`, `.env.example`.** Merge, do not overwrite.

## 3.5 Proposed phase plan

| Phase | Adjustments for this repo | Estimate |
|---|---|---|
| M1 platform | Most of it exists. Add `docker/my.cnf`, bootstrap Makefile targets, CI (Python + DB + frontend jobs), root `CLAUDE.md` and doc stubs. Neo4j stays in compose | half a day |
| M2 schema | Add `sql/schema.sql` and `sql/kg_schema.sql` from the bootstrap and `tests/test_schema.py`. No renames needed (no name clashes). `sql/corpus_schema.sql` stays as is | half a day |
| M3 data | LitSearch download and NOTES, loaders, Colab notebook (human runs it), `load_vectors.py` with bytes binding and index last. Wikipedia data stays loaded in its own tables. Split into M3a (data, notebook) and M3b (vectors, index) around the Human Colab run | 1 to 2 days, plus Colab time |
| M4 search in SQL | `sql/*.sql` + new functions in `citehop/search.py`. `SEARCH_ENGINE=citehop\|proto` flag in the API. Port S02 support as a rerank term | 2 days |
| M5 evaluation | `metrics.py`, `sql/grade.sql`, `runs` table, SciFact check, index sweep. Grade P, A, B, C on dev | 1 to 2 days |
| M6 knowledge graph | Needs `S2_API_KEY`, human gold labels, and an approved LLM cost estimate. Agent prepares templates and scripts. Split into M6a (enrichment, templates, cost), M6b (extraction, merge candidates) and M6c (load, K and L) around the Human steps | 2 to 3 days of agent work, plus human time |
| M7 experiments | Reuse the S03 freeze guard for weight tuning. One test run of A to L and P | 1 day |
| M8 product and production | Re-point Search and Graph views at the new API and `kg_links`. Then, in separate commits: remove the Neo4j path and service, remove the `proto` search path and flag, retire Wikipedia tables. Prod containers, backups, load test, security, scripts and RUNBOOK | 3 to 4 days |

Planned removals (all deferred to M8, each listed again in its phase report):
- Neo4j service, `citehop/graph/`, `tests/test_graph_neo4j.py`, `make graph-*`. Replaced by SQL CTEs over `kg_links`.
- `SEARCH_ENGINE=proto` path and chunk-level search. Replaced by `search.fused()`. Only after config P is recorded.
- Wikipedia tables and loaders, unless kept as a demo extra (decision 1).

## Decisions needed

1. Add `CITEHOP_BOOTSTRAP.md` (and commit `MIGRATION_HANDOFF.md`).
2. Branch and PR target (see Blockers 3).
3. Approve or change recommendations 1 to 12 in section 3.3.
