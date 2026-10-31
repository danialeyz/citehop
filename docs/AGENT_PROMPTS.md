# CiteHop agent starting prompts

Current stack: Next.js/React + Tailwind CSS, FastAPI, MariaDB, Neo4j. These 14 core prompts replace the earlier 12-card set; do not mix task IDs across revisions.

Copy one block into a session whose checkout contains these planning files and completed dependencies. Run C01–C14 in order for the simplest workflow. Each prompt authorizes one task, not delegation. S01–S03 are optional after C14. Full acceptance criteria live in COURSE_TASKS.md; architecture and UI specifications are linked there.

## C01 — Align the stack and local development

Prerequisites: none.

```text
Implement C01 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C01 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Align obsolete paper/Streamlit guidance with the new scope. Scaffold Next.js App Router + React + TypeScript + Tailwind in frontend/, FastAPI in citehop/api/, and local Compose services for MariaDB and Neo4j Community. Keep business logic in citehop/. Pin compatible releases after checking official docs; commit dependency locks and state the Node/Python versions. Add health checks, persistent volumes, environment examples, SQL runner, and documented dev commands. Do not implement feature endpoints yet.

Complete every Done/check item for C01; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C01.
```

## C02 — Acquire Wikipedia and prepare ground truth

Prerequisites: C01.

```text
Implement C02 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C02 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Build revision-pinned cached acquisition for 100 English ML articles and a 10-article smoke subset. Save titles, URLs, revision IDs, text, categories, and internal links with provenance/attribution notes. Draft 30 evidence-backed questions in eval/questions.json: 10 dev and 20 test, including filtered and separately tagged unanswerable cases. Mark drafts unreviewed until checked by a team member.

Complete every Done/check item for C02; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C02.
```

## C03 — Create and load the MariaDB corpus

Prerequisites: C02.

```text
Implement C03 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C03 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Create articles, article_categories, article_links, and chunks with keys/constraints, FULLTEXT, metadata indexes, and VECTOR(768) plus vector index. Implement batched article/category/link loading and a short data-model document. Make revision changes invalidate old chunks/embeddings and advance the corpus version. MariaDB remains the source of truth.

Complete every Done/check item for C03; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C03.
```

## C04 — Build the Neo4j graph projection and queries

Prerequisites: C03.

```text
Implement C04 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C04 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Implement an explicit graph import CLI from MariaDB to Neo4j: Article nodes, Category nodes, LINKS_TO and IN_CATEGORY relationships. Use stable IDs, uniqueness constraints, parameterized Cypher, idempotent batches, and a corpus-version marker set complete only after validation. Reconcile deleted edges/nodes within the CiteHop namespace only. Add bounded neighborhood/path functions and graph status; retain the previous complete snapshot or report rebuilding after interrupted imports.

Complete every Done/check item for C04; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C04.
```

## C05 — Chunk and embed reproducibly

Prerequisites: C03.

```text
Implement C05 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C05 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Implement deterministic 300-token chunks with 50-token overlap using the model tokenizer and a resumable BGE 768-dimensional embedding CLI. Record model/tokenizer revision, normalization, input formatting, configuration hashes, and actual lengths. Account for title/prefix tokens and avoid silent truncation. Invalidate stale embeddings; keep downloads and caches out of git.

Complete every Done/check item for C05; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C05.
```

## C06 — Implement native retrieval and SQL filtering

Prerequisites: C05.

```text
Implement C06 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C06 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Implement keyword and vector search with MariaDB FULLTEXT and VEC_DISTANCE_COSINE, metadata joins, category/length/linked-from filters before final limit, bounded k, and deterministic result handling. Add an exact cosine baseline over the same eligible rows, a CLI query, and three runnable SQL examples with observed plans. Keep retrieval independent of Neo4j.

Complete every Done/check item for C06; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C06.
```

## C07 — Generate bounded answers with citations

Prerequisites: C06.

```text
Implement C07 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C07 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Implement citehop.rag using one generator integration, supplied passage labels, and the shared token limits. Empty hits cause no model call. Reject unknown citation labels; distinguish insufficient evidence from provider failure. Treat retrieved instructions as data. Check existing model access first; request a missing model/access decision while completing independent code and mocked tests.

Complete every Done/check item for C07; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C07.
```

## C08 — Evaluate retrieval and answer grounding

Prerequisites: C07; reviewed C02 labels before final measurements.

```text
Implement C08 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C08 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Build an evaluator writing raw ranks/timings/answers and a versioned manifest. Compare keyword/vector article-level Recall@5, deduplicating by best chunk rank before the five-article cutoff; retrieve enough candidates or exhaust eligible rows. Report filter cases separately and compare ANN with exact retrieval on dev. Run each answerable test retrieval question three times. Separate retrieval, embedding, and generation timing. Prepare 10 saved answers for human review.

Complete every Done/check item for C08; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C08.
```

## C09 — Expose the FastAPI application contract

Prerequisites: C04, C07, C08 evaluator format; final reviewed results may still be pending.

```text
Implement C09 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C09 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Implement validated FastAPI routes for search, answer, article browsing/detail, graph neighborhood/path/status, corpus statistics, and saved evaluation runs/CSV. Reuse package logic and define request/response schemas in OpenAPI. Resolve answer chunk IDs against MariaDB and corpus version instead of trusting browser passage text. Return graph truncation/version/error status explicitly. Add a single typed frontend client derived from the API schema.

Complete every Done/check item for C09; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C09.
```

## C10 — Build the visual shell and Library

Prerequisites: C09.

```text
Implement C10 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C10 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Build responsive Next.js routes for Search, Library, Graph, and Dashboard using shared React components and Tailwind tokens. Add paginated article browsing, title/category filters, source detail, stored passages, and links to graph exploration. Use the existing logo, dark navy surfaces, cyan accents, and deliberate typography. Use honest empty states for views wired in later cards.

Complete every Done/check item for C10; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C10.
```

## C11 — Deliver the polished search and RAG flow

Prerequisites: C07, C10.

```text
Implement C11 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C11 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Build the search hero, reviewed dev examples, Keyword/Meaning selector, compact filters, ranked source cards, explicit Generate answer action, and exact-passage citation inspector. Add Explore connections actions that carry the selected article and search context into Graph. Invalidate answers on query/filter changes, ignore stale request responses, and preserve useful state on navigation.

Complete every Done/check item for C11; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C11.
```

## C12 — Build the interactive knowledge graph

Prerequisites: C04, C10.

```text
Implement C12 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C12 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Use React Flow custom article/category nodes and a deterministic layout computed on graph changes. Deliver pan/zoom/fit/minimap, node selection, controlled expansion, category toggle, degree emphasis, directional edge labels, search-to-graph highlighting, and an evidence inspector. Add a two-article path interaction backed by the bounded path endpoint. Keep node positions stable on expansion and support reset/back navigation. This is a read-only explorer, not a graph editor.

Complete every Done/check item for C12; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C12.
```

## C13 — Build the corpus and evaluation dashboard

Prerequisites: C08, C10.

```text
Implement C13 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C13 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Build corpus cards, embedding coverage, graph projection status/counts, saved-run and split selectors, keyword/vector Recall@5 and median/p95 latency charts, grounding review counts, accessible comparison table, and CSV export. Distinguish live corpus/graph snapshots from saved evaluation versions. Put model/chunk/index/timing details in an expandable panel.

Complete every Done/check item for C13; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C13.
```

## C14 — Integrate and prepare the course submission

Prerequisites: C11, C12, C13.

```text
Implement C14 from docs/COURSE_TASKS.md. Read its Project definition, Agent handoff, Shared contracts, and C14 card, then only the listed inputs and relevant architecture/UI sections. Follow applicable repository instructions and verify prerequisites in the checkout.

Reproduce setup through graph import, retrieval, answer generation, and all four views against isolated local databases. Finish README, model/chunk/index rationale, measured findings, team credits, tracked screenshots, and a five-minute demo script. Explain the split: MariaDB demonstrates native vector/SQL retrieval; Neo4j powers derived relationship exploration. Document extra memory/import cost and snapshot consistency limitations.

Complete every Done/check item for C14; report blocked checks honestly. Keep the course-project scope and reuse existing code. Preserve unrelated changes; do not rename branches or publish. Report files changed, checks/results, and exact blockers in at most 8 bullets. Stop after C14.
```

## S01 — Optional: Reciprocal rank fusion

Prerequisites: C14; this prompt opts into S01 only.

```text
Implement S01 from docs/COURSE_TASKS.md. Read the shared contracts, S01 card, and relevant architecture sections; verify C14 is complete. Follow repository instructions.

Add RRF over top-50 keyword/vector lists with constant 60. Reuse filters and output contracts; test exact scores, overlaps, ties, and provenance. Run one frozen-set comparison with recall and latency; no parameter sweep.

Run the card's checks and relevant tests/lint. Preserve unrelated work; do not rename branches or publish. Report changed files, measured results, and blockers in at most 8 bullets. Stop after S01.
```

## S02 — Optional: Graph-assisted retrieval experiment

Prerequisites: C14; this prompt opts into S02 only.

```text
Implement S02 from docs/COURSE_TASKS.md. Read the shared contracts, S02 card, and relevant architecture sections; verify C14 is complete. Follow repository instructions.

Use Neo4j to expand at most 10 retrieval seeds to 100 distinct one-hop article neighbors, then fetch eligible chunks in MariaDB. Define deterministic ranking and enforce the original SQL filters. Test caps, cycles, deduplication, stale graph, and outage. Compare recall/latency with core vector retrieval and record graph version. Keep this separate from the core graph visualization.

Run the card's checks and relevant tests/lint. Preserve unrelated work; do not rename branches or publish. Report changed files, measured results, and blockers in at most 8 bullets. Stop after S02.
```

## S03 — Optional: One chunk-size experiment

Prerequisites: C14; this prompt opts into S03 only.

```text
Implement S03 from docs/COURSE_TASKS.md. Read the shared contracts, S03 card, and relevant architecture sections; verify C14 is complete. Follow repository instructions.

Compare 200/50 chunking against 300/50 on dev with the same corpus/model/questions. Isolate configurations so the demo keeps working. Record chunk count, embedding effort, recall, and latency; freeze the choice before a labeled follow-up test run. No test-set tuning.

Run the card's checks and relevant tests/lint. Preserve unrelated work; do not rename branches or publish. Report changed files, measured results, and blockers in at most 8 bullets. Stop after S03.
```
