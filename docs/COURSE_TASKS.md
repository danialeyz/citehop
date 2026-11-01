# CiteHop: native vector RAG with a visual knowledge graph

Current plan: Next.js/React + Tailwind CSS, FastAPI, MariaDB, and Neo4j, as requested. This supersedes the earlier 12-card plan: IDs have been revised, so use the matching current prompts. Core tasks C01–C14 are implemented; see [SUBMISSION.md](SUBMISSION.md) for the C14 reproduction, checks, and open items (human review, `main` branch). Optional tasks S01–S03 are not started.

## Project definition

CiteHop answers questions from a small Wikipedia corpus, cites the retrieved passages, and lets users explore the connected articles in a polished interactive knowledge graph. Core screens: Search, Library, Graph, Dashboard.

Keep the [MariaDB area 4 assignment](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively) central: native vectors, semantic retrieval with SQL predicates/joins, measured recall/latency, and a reproducible tutorial. Neo4j supplements MariaDB for graph exploration; it does not replace its vector index or relational filtering. RAG generation runs in Python. The supplied brief does not establish whether the professor has extra restrictions on a second database; disclose Neo4j in the submission and keep the required MariaDB demonstration self-contained.

Scope: 100 English ML Wikipedia articles, 10-article smoke subset, 30 checked questions, one embedder, one generator, local deployment only. No auth, cloud hosting, background synchronization, queue, separate vector store, LLM entity extraction, or broad experiment grid. The graph uses real article links and categories; it must not imply those links are scholarly citations or inferred semantic relationships.

Architecture decisions and endpoint details: [ARCHITECTURE.md](ARCHITECTURE.md). Visual acceptance criteria: [design/COURSE_UI.md](design/COURSE_UI.md). Copy-ready prompts: [AGENT_PROMPTS.md](AGENT_PROMPTS.md).

## Agent handoff

Read Project definition, Shared contracts, your card, and only its relevant inputs. Implement one card, verify its dependencies against actual files, run its checks, and stop. Report changed files, checks/results, and precise blockers in at most 8 bullets. Preserve unrelated work; do not rename branches, publish, or delegate automatically. Keep secrets/caches out of git. Mock network/model calls for unit tests, but use real smoke runs as acceptance evidence. Never invent metrics or treat screenshots of fixtures as a working integration.

## Shared contracts

- `frontend/`: Next.js App Router, React, TypeScript, Tailwind. `citehop/api/`: FastAPI routes/schemas. `citehop/`: retrieval, RAG, ingestion, graph, evaluation. SQL/Cypher stay behind FastAPI; the browser never connects to either database. Retire Streamlit during C01.
- Python 3.11, existing MariaDB connector, MariaDB 11.8.9 initially, BGE base English v1.5 with 768 dimensions. C01 verifies support and pins compatible frontend/API/Neo4j versions using official docs; do not hard-code guessed current versions into this plan.
- MariaDB owns `articles`, `article_categories`, `article_links`, `chunks` with vectors. IDs are stable; document exact types in C03. Data/embedding changes produce a new corpus/config identifier. Graph status names the imported version.
- Neo4j derives `Article` and `Category` nodes with `LINKS_TO` and `IN_CATEGORY` edges. Manual versioned import; no request-time dual writes. Core search works when Neo4j is down. Graph queries are one hop by default, two hops maximum, 50 nodes/100 edges default, 100 nodes/200 edges hard caps, plus query timeout and deterministic truncation.
- Chunk default: 300 tokenizer tokens, overlap 50; include title/prefix in model-limit checks. Cache by revision/text/config hash. Record model revision, formatting, normalization, and tokenizer. No silent truncation.
- Python `search(query, method="vector", filters=None, k=5)` returns chunk/article IDs, title, source URL, passage, rank, score, and method. Keyword uses MariaDB FULLTEXT; vector uses cosine. Category, article-length, and linked-from predicates apply in SQL before final limit. Do not compare scores across methods as probabilities.
- Python `answer(question, hits)` returns text, citation mapping, and status. At most five passages, 1,800 context tokens, 300 output tokens, one explicit generation call. Empty evidence does not call a model. Unknown labels invalidate the answer; valid labels do not prove factual support.
- Freeze 10 dev and 20 test questions before tuning. Relevant article IDs, supporting passages, filters, answerability, and human review status are stored. Unreviewed labels block final claims, not harness development. Recall is article-level; report unanswerable cases and grounding review separately.
- Saved runs include raw output, IDs/version/config, split, denominators, latency units/boundaries, hardware, warm-up policy, and human review counts. Missing values are null, not zero. Dashboards read saved runs and live counts separately; no benchmark or generation on page load.
- All core cards include appropriate focused tests. UI cards add lint/typecheck/build and visual checks at 1440px/390px. Final integration adds a small browser test of the main user journey. No production testing framework or coverage target.

## Core tasks

Simplest execution order: C01–C14. Dependencies specify what must actually be present; C04 and C05 are independent after C03, but do not assume simultaneous agents or shared edits are safe.

### C01 — Align the stack and local development

**Needs:** none. **Read:** README, Makefile, dependency/env files, app instructions, docs/ARCHITECTURE.md.

**Build:** Align obsolete paper/Streamlit guidance with the new scope. Scaffold Next.js App Router + React + TypeScript + Tailwind in frontend/, FastAPI in citehop/api/, and local Compose services for MariaDB and Neo4j Community. Keep business logic in citehop/. Pin compatible releases after checking official docs; commit dependency locks and state the Node/Python versions. Add health checks, persistent volumes, environment examples, SQL runner, and documented dev commands. Do not implement feature endpoints yet.

**Done/check:** Frontend and API start; both databases pass real connection checks; a tiny MariaDB vector query succeeds. Restart preserves test data. Python package discovery includes new subpackages. Frontend lint/typecheck/build and backend smoke checks pass. No secrets enter browser configuration or git; existing data is preserved.

### C02 — Acquire Wikipedia and prepare ground truth

**Needs:** C01. **Read:** data contracts, scripts/, local setup.

**Build:** Build revision-pinned cached acquisition for 100 English ML articles and a 10-article smoke subset. Save titles, URLs, revision IDs, text, categories, and internal links with provenance/attribution notes. Draft 30 evidence-backed questions in eval/questions.json: 10 dev and 20 test, including filtered and separately tagged unanswerable cases. Mark drafts unreviewed until checked by a team member.

**Done/check:** Real smoke downloads match source records; reruns reuse the pinned snapshot. Missing pages are reported, never silently substituted. Question IDs and relevant articles resolve; filters admit labeled sources. Supply a short human review checklist and preserve review status.

### C03 — Create and load the MariaDB corpus

**Needs:** C02. **Read:** acquisition output, DB helpers, architecture.

**Build:** Create articles, article_categories, article_links, and chunks with keys/constraints, FULLTEXT, metadata indexes, and VECTOR(768) plus vector index. Implement batched article/category/link loading and a short data-model document. Make revision changes invalidate old chunks/embeddings and advance the corpus version. MariaDB remains the source of truth.

**Done/check:** Schema and smoke load reruns preserve counts. Tests cover orphan references, duplicate edges/categories, and changed revisions. Vector index creation works on the pinned server. Record real corpus counts; do not build a generic graph schema or migration framework.

### C04 — Build the Neo4j graph projection and queries

**Needs:** C03. **Read:** data model, docs/ARCHITECTURE.md graph contract.

**Build:** Implement an explicit graph import CLI from MariaDB to Neo4j: Article nodes, Category nodes, LINKS_TO and IN_CATEGORY relationships. Use stable IDs, uniqueness constraints, parameterized Cypher, idempotent batches, and a corpus-version marker set complete only after validation. Reconcile deleted edges/nodes within the CiteHop namespace only. Add bounded neighborhood/path functions and graph status; retain the previous complete snapshot or report rebuilding after interrupted imports.

**Done/check:** Import twice yields identical counts; changed/deleted source records reconcile. A failed import is not marked current. Verify real edges against MariaDB; test cycles, deterministic caps, timeouts, missing nodes, and Neo4j outage. Stale/unavailable graphs do not block MariaDB search. No cross-database atomicity claim or automatic background sync.

### C05 — Chunk and embed reproducibly

**Needs:** C03. **Read:** schema, cached text, ML dependencies.

**Build:** Implement deterministic 300-token chunks with 50-token overlap using the model tokenizer and a resumable BGE 768-dimensional embedding CLI. Record model/tokenizer revision, normalization, input formatting, configuration hashes, and actual lengths. Account for title/prefix tokens and avoid silent truncation. Invalidate stale embeddings; keep downloads and caches out of git.

**Done/check:** Tests cover empty/short input, overlap, stable IDs, and model limits. A real smoke batch produces finite 768-dimensional vectors. Reruns skip completed matching work. Changed text/configuration cannot reuse vectors. Document full/smoke commands, actual counts, and measured runtime.

### C06 — Implement native retrieval and SQL filtering

**Needs:** C05. **Read:** schema, embedding configuration, search contract.

**Build:** Implement keyword and vector search with MariaDB FULLTEXT and VEC_DISTANCE_COSINE, metadata joins, category/length/linked-from filters before final limit, bounded k, and deterministic result handling. Add an exact cosine baseline over the same eligible rows, a CLI query, and three runnable SQL examples with observed plans. Keep retrieval independent of Neo4j.

**Done/check:** Fixtures verify ranking, empty/invalid input, safe parameterization, deduplication, and an eligible hit outside global unfiltered top-k. Real queries work. Compare indexed and exact retrieval; disclose plans that use a scan. Never filter global top-k in Python or call FULLTEXT BM25.

### C07 — Generate bounded answers with citations

**Needs:** C06. **Read:** search contract, environment/model settings.

**Build:** Implement citehop.rag using one generator integration, supplied passage labels, and the shared token limits. Empty hits cause no model call. Reject unknown citation labels; distinguish insufficient evidence from provider failure. Treat retrieved instructions as data. Check existing model access first; request a missing model/access decision while completing independent code and mocked tests.

**Done/check:** Test empty context, invalid labels, provider errors, and embedded instructions. Validate one real grounded answer and one unanswerable question when access is available. Record model/prompt, usage, and generation latency. Sources remain usable if generation fails; mocked output does not count as a live validation.

### C08 — Evaluate retrieval and answer grounding

**Needs:** C07; reviewed C02 labels before final measurements. **Read:** questions, search/RAG APIs, exact baseline.

**Build:** Build an evaluator writing raw ranks/timings/answers and a versioned manifest. Compare keyword/vector article-level Recall@5, deduplicating by best chunk rank before the five-article cutoff; retrieve enough candidates or exhaust eligible rows. Report filter cases separately and compare ANN with exact retrieval on dev. Run each answerable test retrieval question three times. Separate retrieval, embedding, and generation timing. Prepare 10 saved answers for human review.

**Done/check:** Hand-scored fixtures cover repeated article chunks, multiple relevant articles, zero hits, and short lists. Include zero-hit answerable questions in metrics; report unanswerable questions separately. Save medians/p95, sample counts, units, run/split/corpus/config IDs, warm-up policy, and review denominators. Mark absent reviews null. Implement the harness while reviews are pending, but do not invent final results.

### C09 — Expose the FastAPI application contract

**Needs:** C04, C07, C08 evaluator format; final reviewed results may still be pending. **Read:** docs/ARCHITECTURE.md endpoints, package functions.

**Build:** Implement validated FastAPI routes for search, answer, article browsing/detail, graph neighborhood/path/status, corpus statistics, and saved evaluation runs/CSV. Reuse package logic and define request/response schemas in OpenAPI. Resolve answer chunk IDs against MariaDB and corpus version instead of trusting browser passage text. Return graph truncation/version/error status explicitly. Add a single typed frontend client derived from the API schema.

**Done/check:** API tests cover valid requests, invalid filters/limits/IDs, missing runs, malformed files, Neo4j-only outage, stale graph/context, and error redaction. A real API smoke flow retrieves sources and a graph neighborhood. Blocking database/model calls do not block the async event loop. Bounded inference concurrency returns a clear busy response; no automatic generation retries. Next.js proxy and health route work.

### C10 — Build the visual shell and Library

**Needs:** C09. **Read:** docs/design/COURSE_UI.md, existing tokens/logo, typed API client.

**Build:** Build responsive Next.js routes for Search, Library, Graph, and Dashboard using shared React components and Tailwind tokens. Add paginated article browsing, title/category filters, source detail, stored passages, and links to graph exploration. Use the existing logo, dark navy surfaces, cyan accents, and deliberate typography. Use honest empty states for views wired in later cards.

**Done/check:** Library uses real API data. Filter/page changes reset pagination correctly and returning from detail preserves list state. Check keyboard focus, long titles, and 1440px/390px layouts. Frontend lint/typecheck/build pass. Save screenshots under .context/. No fabricated data, dead buttons, or browser database credentials.

### C11 — Deliver the polished search and RAG flow

**Needs:** C07, C10. **Read:** UI spec, search/answer endpoints, shared components.

**Build:** Build the search hero, reviewed dev examples, Keyword/Meaning selector, compact filters, ranked source cards, explicit Generate answer action, and exact-passage citation inspector. Add Explore connections actions that carry the selected article and search context into Graph. Invalidate answers on query/filter changes, ignore stale request responses, and preserve useful state on navigation.

**Done/check:** An actual query-to-answer-to-citation flow works; graph navigation preserves its seed. Exercise no hits, insufficient evidence, missing embeddings, provider failure, and DB outage. Remounts/rerenders do not generate twice. Text is escaped; cited IDs resolve to exact stored passages. Save desktop/mobile screenshots and run one browser smoke test for the critical flow.

### C12 — Build the interactive knowledge graph

**Needs:** C04, C10. **Read:** UI graph specification, graph endpoints, React Flow official docs.

**Build:** Use React Flow custom article/category nodes and a deterministic layout computed on graph changes. Deliver pan/zoom/fit/minimap, node selection, controlled expansion, category toggle, degree emphasis, directional edge labels, search-to-graph highlighting, and an evidence inspector. Add a two-article path interaction backed by the bounded path endpoint. Keep node positions stable on expansion and support reset/back navigation. This is a read-only explorer, not a graph editor.

**Done/check:** Every node/edge resolves to recorded source data; capped results visibly say truncated. Test dense/cyclic graphs up to 100 nodes/200 edges, disconnected seeds, stale projection, server timeout, and Neo4j outage. Path display explains traversal direction and the three-hop scope. Keyboard users can use an equivalent connection list. Record measured interaction behavior on the demo machine; no continuous layout simulation. Save real-data desktop/mobile screenshots.

### C13 — Build the corpus and evaluation dashboard

**Needs:** C08, C10. **Read:** UI spec, stats/runs API, graph status.

**Build:** Build corpus cards, embedding coverage, graph projection status/counts, saved-run and split selectors, keyword/vector Recall@5 and median/p95 latency charts, grounding review counts, accessible comparison table, and CSV export. Distinguish live corpus/graph snapshots from saved evaluation versions. Put model/chunk/index/timing details in an expandable panel.

**Done/check:** Values match real DB/API counts and one saved run. Run selection updates all charts together; incompatible configurations are not silently compared. No-run, no-review, malformed-output, stale graph, and service-outage states are clear. Units and denominators are visible. Loading the dashboard triggers no model call or benchmark. Save desktop/mobile screenshots.

### C14 — Integrate and prepare the course submission

**Needs:** C11, C12, C13. **Read:** implemented commands, saved evidence, assignment, architecture.

**Build:** Reproduce setup through graph import, retrieval, answer generation, and all four views against isolated local databases. Finish README, model/chunk/index rationale, measured findings, team credits, tracked screenshots, and a five-minute demo script. Explain the split: MariaDB demonstrates native vector/SQL retrieval; Neo4j powers derived relationship exploration. Document extra memory/import cost and snapshot consistency limitations.

**Done/check:** Run backend tests, DB/graph integration checks, frontend lint/typecheck/build, and a browser flow search → citation → graph → dashboard. Trace metrics to saved evidence and explicitly list blocked checks. Preserve existing volumes. Review the assignment checklist; record public-repository/main-branch requirements without renaming or publishing. Verify setup is runnable without hidden local state.

## Optional tasks after C14

Each is a separate opt-in task.

### S01 — Reciprocal rank fusion

**Needs:** C14. **Read:** relevant retrieval/graph/embedding implementation and evaluator.

**Build and check:** Add RRF over top-50 keyword/vector lists with constant 60. Reuse filters and output contracts; test exact scores, overlaps, ties, and provenance. Run one frozen-set comparison with recall and latency; no parameter sweep.

### S02 — Graph-assisted retrieval experiment

**Needs:** C14. **Read:** relevant retrieval/graph/embedding implementation and evaluator.

**Build and check:** Use Neo4j to expand at most 10 retrieval seeds to 100 distinct one-hop article neighbors, then fetch eligible chunks in MariaDB. Define deterministic ranking and enforce the original SQL filters. Test caps, cycles, deduplication, stale graph, and outage. Compare recall/latency with core vector retrieval and record graph version. Keep this separate from the core graph visualization.

### S03 — One chunk-size experiment

**Needs:** C14. **Read:** relevant retrieval/graph/embedding implementation and evaluator.

**Build and check:** Compare 200/50 chunking against 300/50 on dev with the same corpus/model/questions. Isolate configurations so the demo keeps working. Record chunk count, embedding effort, recall, and latency; freeze the choice before a labeled follow-up test run. No test-set tuning.

## Sources and status

The [assignment](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively) supplies the course context. Stack and graph requirements come from the user; corpus size, architecture, and visual limits are project decisions. The original ZIP contained no task cards, so no original-card equivalence is claimed. This revision defines the architecture and work; it does not claim the application is implemented or update Notion.
