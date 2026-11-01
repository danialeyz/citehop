# CiteHop migration handoff: prototype to target architecture

This file tells a coding agent (Claude Code) how to move an existing prototype to the CiteHop architecture without breaking what already works. The agent audits first, migrates in small phases, and stops for human approval between phases.

---

## 0. How to use (for Danial)

1. Put this file in the root of the prototype repo, next to `CITEHOP_BOOTSTRAP.md` (from the Databases project). The bootstrap file holds the exact target files (schema, Makefile, Docker, tests).
2. Commit or stash everything, then create a branch: `git checkout -b migrate/citehop`.
3. Open Claude Code in the repo and paste:

```text
Read MIGRATION_HANDOFF.md and CITEHOP_BOOTSTRAP.md completely.
Do Phase M0 (audit) only. Write docs/MIGRATION_AUDIT.md and stop.
Do not change any code until I approve the audit.
Follow section 2 (rules) at all times.
```

4. Review the audit. Then say "go M1", "go M2" and so on, one phase at a time.

Reference links (private until shared):
- Design: https://claude.ai/artifact/Xm3zXFbuHntBrVcBos1ajw
- Graph Explorer: https://claude.ai/artifact/3tWT2zVd9Yma8QagZMGbXQ
- Task board: https://app.notion.com/p/41ef857fb23f4e259802f67962a207f9 (cards are referenced as #N below)

---

## 1. The target in one paragraph

CiteHop is a scientific paper search engine that runs entirely inside **MariaDB 11.8.9**. It searches the **LitSearch** benchmark (64,183 ML/NLP papers, 597 questions with answers, MIT licence) in three ways:
- keyword search with a FULLTEXT index
- meaning search with a `VECTOR(768)` column from `BAAI/bge-base-en-v1.5` and a cosine HNSW index
- graph search over citations, authors and LLM-extracted concepts, using recursive CTEs

Results are fused with RRF and reranked with one weighted score. Twelve configurations (A to L) are graded in SQL against the answer key. A FastAPI service serves search and the graph to a search page and the Graph Explorer, deployed with Docker, Caddy and a release pipeline.

---

## 2. Rules for the agent (hard)

**Migration rules**
1. **Audit before code.** Phase M0 changes nothing except writing `docs/MIGRATION_AUDIT.md`.
2. **Keep it running.** After every phase the prototype's main user flow still works, or the audit says explicitly which flow is replaced and by what.
3. **No silent deletions.** Before removing any prototype file, feature or table, list it in the phase report with the reason and what replaces it.
4. **Adapt, don't rewrite, what already matches.** If prototype code already meets a target requirement, keep it and adjust names or paths. Rewrite only where the audit marks a gap.
5. **Old and new side by side when switching engines.** Build the new path, prove it with tests and numbers, then switch callers, then delete the old path in a separate commit.
6. **One branch, one commit per phase:** `migrate M<n>: <what>`. Open a PR per phase into `migrate/citehop`.

**Target rules** (also in CITEHOP_BOOTSTRAP.md section 2)
7. Pin `mariadb:11.8.9`. Never `lts` or `latest`.
8. Every vector index uses `DISTANCE=cosine`.
9. Vector search has exactly this shape: `ORDER BY VEC_DISTANCE_COSINE(col, ?) LIMIT k`. Compute `1 - d` outside.
10. Vector indexes are added after bulk loading, never in a schema file. No other index is added to a table after its vector index exists.
11. Vectors are bound as bytes, `np.asarray(v, dtype="<f4").tobytes()`, after a length check.
12. Never guess LitSearch field names. Read them from `data/NOTES.md` (card #9).
13. Never tune on the test split.
14. Every recursive CTE has a depth limit.
15. No secrets in git, and no SQL built with f-strings.
16. Docs: short sentences, plain words, no em dashes.
17. **Stop and ask** before: dropping data, changing a pinned version, changing the corpus or the embedding model, any step that costs money, or when a check fails twice.

---

## 3. Phase M0: audit (no code changes)

Read the whole prototype. Write `docs/MIGRATION_AUDIT.md` with these sections.

### 3.1 What exists
A short table:
- language and framework
- database engine and version
- vector store (in DB, separate service, or files)
- corpus and its size
- embedding model and dimensions
- search modes
- any graph data
- evaluation (questions, metrics)
- UI
- API
- tests
- CI
- deployment

Cite file paths for each row.

### 3.2 Gap table
One row per target capability from section 4. Columns:
- Capability
- Status: Done / Partial / Missing / Conflicts
- Where in the prototype
- What has to change
- Effort: S (under 2 h), M (half a day), L (a day or more)
- Notion card(s)

### 3.3 Conflicts that need a human decision
Anything where the prototype took a different path from the target. Say what the prototype does, what the target does, and recommend one option with one sentence why. Typical ones:
- a different database
- a different corpus
- a different embedding model
- a separate vector database
- a different UI framework

See section 5 for the default recommendation in each case.

### 3.4 Keep list
Prototype parts that are better than or equal to the target and should be kept, for example a nicer UI or a working ingestion cache.

### 3.5 Proposed phase plan
The phases from section 6 with any adjustments for this prototype, and an estimate per phase.

**Check:** the audit exists, every row in 3.2 is filled, and no file other than `docs/MIGRATION_AUDIT.md` changed (`git status`).
**Then stop and wait for approval.**

---

## 4. Target capabilities (the checklist the audit compares against)

### 4.1 Platform
| # | Capability | Cards |
|---|---|---|
| P1 | Docker `mariadb:11.8.9` with `my.cnf` (`mhnsw_max_cache_size=1G`, `innodb_ft_min_token_size=2`) | #2 |
| P2 | Python package `citehop/`, Makefile targets, `.env` config, ruff, pytest (unit + `db` marker) | #6 |
| P3 | CI with a MariaDB 11.8.9 service that applies the schema twice and runs the db tests | #6 |
| P4 | Docs: `CLAUDE.md`, `README.md`, `docs/` (ARCHITECTURE, DATA_MODEL, DECISIONS, EXPERIMENTS, RESULTS, TRAPS, GLOSSARY, CONTRIBUTING) | #6, #31 |

### 4.2 Data model (exact DDL in CITEHOP_BOOTSTRAP.md 4.9 and 4.10)
| # | Table or view | Purpose |
|---|---|---|
| D1 | `papers` (corpusid PK, title, abstract, year, n_cited_by, venue_id, FULLTEXT) | one row per paper |
| D2 | `citations` (citing_id, cited_id PK, reverse key) | the citation graph |
| D3 | `emb_bge_base` (corpusid PK, `emb VECTOR(768) NOT NULL`) | meaning, one table per model |
| D4 | `queries`, `qrels` | 597 questions and the answer key, with kind, origin and split |
| D5 | `runs` (config, query_id, rnk PK, score, `found_via SET('kw','vec','cite','concept','author')`) | every graded result |
| D6 | `authors`, `paper_authors`, `venues` | metadata graph |
| D7 | `concepts` (with `VECTOR(768)`, df), `concept_aliases`, `paper_concepts` (with evidence quote) | LLM concept graph |
| D8 | view `kg_links (a, b, rel)` | every link in both directions, for exploring |
| D9 | `search_log` (hash only, no raw query) | production observability |

### 4.3 Data pipeline
| # | Step | Cards |
|---|---|---|
| L1 | Download LitSearch, record exact fields in `data/NOTES.md` | #9 |
| L2 | Load papers and in-corpus citations, fill `n_cited_by` | #10 |
| L3 | Load questions, qrels, a stratified 20/80 dev/test split with seed 42 | #12 |
| L4 | Embed on Colab with bge-base, check, bulk load, then add the cosine index | #13, #14, #15 |
| L5 | Enrich authors, venues and years from Semantic Scholar | #12.7 |
| L6 | 50-abstract gold set, LLM extraction with quote verification, concept merge and load | #13.5, #14.5, #15.5 |

### 4.4 Search pipeline (SQL in the design page, section 05)
| # | Step | Cards |
|---|---|---|
| S1 | Keyword: `MATCH ... AGAINST` natural language mode, top 100 | #16 |
| S2 | Meaning: exact vector query shape, top 100, EXPLAIN proves the index | #17 |
| S3 | RRF fusion in SQL with `UNION ALL` + `GROUP BY`, top 10 seeds | #18 |
| S4 | Citation expansion: recursive CTE, both directions, 1 to 2 hops, weighted by seed similarity, halved per hop, divided by `LOG(2 + n_cited_by)` | #22 |
| S5 | Shared references and cited-together self-joins | #23 |
| S6 | Concept expansion (config K, IDF-weighted) and author expansion (config L) | #23.5, #23.6 |
| S7 | Rerank: `a*meaning + b*graph + c*popularity (+ concept, author)`, each scaled 0 to 1 | #24 |

### 4.5 Evaluation
| # | Capability | Cards |
|---|---|---|
| E1 | `evaluate.py`: fills `runs`, prints Recall@5 (specific), Recall@20 (broad), nDCG@10, MRR; SQL and Python agree | #19 |
| E2 | SciFact sanity check, nDCG@10 near 74.04 | #20 |
| E3 | Index sweep: exact vs HNSW over ef_search and M, then choose a setting with recall of at least 0.95 | #21 |
| E4 | Weight tuning on dev only | #25 |
| E5 | Configs A to L on test, with paired bootstrap intervals vs C | #26 |
| E6 | Latency p50 and p95 per config | #27 |

### 4.6 Product and production
| # | Capability | Cards |
|---|---|---|
| U1 | Search page showing how each paper was found (keyword, meaning, citation path) | #28 |
| U2 | Graph Explorer on real data (2-hop subgraph, node cap, path view, SQL panel) | #28.5 |
| A1 | FastAPI: `/health`, `/search`, `/paper/{id}`, `/graph/{id}`, validated inputs, fake embed backend for CI | #32 |
| A2 | Read-only DB user, connection pool, `max_statement_time` | #33 |
| A3 | `search_log` + JSON logs | #34 |
| O1 | Production containers (db, api, app, caddy); model baked in; non-root | #35 |
| O2 | Snapshot, nightly backup, restore drill with golden queries | #36 |
| O3 | Load test and budget | #37 |
| O4 | Security checklist and CI checks | #38 |
| O5 | Deploy with HTTPS, release pipeline with rollback, uptime check, runbook | #39 to #42 |

---

## 5. Default answers for common conflicts

Write these into the audit as recommendations. A human decides.

| Prototype does | Recommendation | Why |
|---|---|---|
| PostgreSQL + pgvector | Move to MariaDB 11.8.9. Keep the Postgres code only until M3 passes, then delete it. | The course project is about MariaDB's native vectors. Keeping two engines doubles the work. |
| A separate vector store (Chroma, FAISS, Qdrant, Pinecone) | Move vectors into `emb_bge_base`. | The core idea is one engine for text, vectors and the graph, joined in SQL. |
| A different corpus (Wikipedia, arXiv sample, own PDFs) | Switch to LitSearch for the graded experiments. Keep the old corpus loader behind a flag only if it's a demo extra. | LitSearch brings the answer key and citation links. Without it there is no measurable result. |
| A different embedding model | Keep it as a second table `emb_<model>` and add bge-base as the default. Compare both on dev. | One vector index per table makes side-by-side models cheap, and the comparison is a free extra result. |
| Embeddings computed per request or kept in Python memory | Precompute, store in MariaDB, and query with the exact vector shape. | Otherwise the index and the latency numbers mean nothing. |
| Search logic in the frontend or in Python loops | Move ranking, fusion and graph walks into SQL files under `sql/`, called from `citehop/search.py`. | The SQL is the course deliverable, and it must be explainable line by line. |
| A UI framework other than Streamlit (Next.js, React) | Keep it. Point it at the FastAPI service (#32) instead of the DB. | The target only requires that the page shows `found_via` and the citation path. The framework is free. |
| No evaluation | Add E1 before changing any ranking logic. | Every later change needs a number to prove it helped. |
| LLM answer generation (RAG answers) | Keep it as an optional mode, but don't grade it. Grading is retrieval only (Recall, nDCG, MRR). | LitSearch labels papers, not answers. |

---

## 6. Migration phases

Each phase lists its goal, steps, Check and stop conditions. Run `make lint && make test` (and `make test-db` once M1 is done) before every commit.

### M1: platform alignment (cards #2, #6)
1. Add `docker/`, `Makefile`, `pyproject.toml`, `requirements*.txt`, `.env.example`, `.editorconfig` and `.gitignore` from the bootstrap. Merge them with any existing ones; don't overwrite them blindly.
2. Add `citehop/db.py`, `apply_sql.py` and `check.py`. If the prototype has its own connection code, make it call `citehop.db.connect()`.
3. Add CI from bootstrap 4.21. Keep any existing jobs.

**Check:** `make db-up && make check` prints `OK ... 11.8.9`, and the prototype's main flow still runs.
**Stop if:** the prototype needs a different DB engine to keep running. Then run both engines in compose until M3.

### M2: schema (cards #8, #12.5)
1. Add `sql/schema.sql` and `sql/kg_schema.sql` exactly as in the bootstrap.
2. If the prototype has tables with the same names, rename them to `proto_<name>` in a migration script. Don't drop them.
3. Add `tests/test_schema.py`.

**Check:** `make schema kg-schema` passes twice, and `make test-db` passes.
**Stop if:** a prototype table must be dropped. List it and ask.

### M3: data (cards #9, #10, #12, #13 to #15)
1. Run `make inspect` and fill in `data/NOTES.md`.
2. Write `load_corpus.py` and `load_questions.py`, reusing any prototype download or cache code that already works.
3. Embeddings:
   - If the prototype already has bge-base vectors for LitSearch, convert them to the `.npy` pair and check them.
   - Otherwise, create the Colab notebook. A human runs it.
4. Run `load_vectors.py`, adding the cosine index last.
5. If the prototype used another model, load its vectors into `emb_<model>` too (section 5).

**Check:** the row counts match (64,183 papers, 597 queries), and a paper's own title finds it at rank 1.
**Stop if:** embedding needs a paid API or GPU time nobody has approved.

### M4: search in SQL (cards #16, #17, #18, #22, #23, #24)
1. Write the SQL files in `sql/` and the matching functions in `citehop/search.py`.
2. Point the prototype's search entry point at `search.fused()`, behind a feature flag `SEARCH_ENGINE=citehop|proto`, so both can be compared.
3. Port any good prototype ranking idea as an extra rerank term, not as a parallel path.

**Check:**
- EXPLAIN shows the fulltext index and `vx_emb`.
- The fixture tests for the CTE and the rerank pass.
- The prototype UI returns results with `SEARCH_ENGINE=citehop`.

### M5: evaluation (cards #19, #20, #21)
1. Add `evaluate.py`, `metrics.py` and `sql/grade.sql`, plus the SciFact check and the index sweep.
2. Grade the prototype's old search as config `P` on dev. It's the "before" number.

**Check:** dev numbers exist for P, A, B and C; SciFact is near 74; the index setting is chosen and recorded in DECISIONS.
**Stop if:** SciFact is more than 5 points off. Debug before going on.

### M6: knowledge graph (cards #12.7, #13.5, #14.5, #15.5, #23.5, #23.6)
1. Enrichment needs `S2_API_KEY`. Ask if it's missing.
2. The gold labels are a human task. The agent only prepares the templates and the agreement script.
3. Extraction requires approval of a cost estimate on 100 abstracts first.
4. Concept merges need human review before loading.
5. Add configs K and L.

**Check:** concept and author coverage numbers are in RESULTS, and K and L run on dev.

### M7: experiments (cards #25, #26, #27)
1. Tune on dev, run A to L (plus P) on test once, then bootstrap and measure latency.

**Check:** `results/main_table.csv` is complete, and RESULTS and DECISIONS are updated.
**Stop if:** you are tempted to change anything after seeing the test numbers. Record it as a limit instead.

### M8: product and production (cards #28, #28.5, #32 to #43)
1. If the prototype UI is kept, add `found_via` tags, the citation path and the Graph Explorer view, fed by the API.
2. Add the API, read-only user, logging, containers, backups, load test and security pass, as their cards describe.
3. Deploy (#39) and release (#43) are human tasks. The agent prepares scripts and RUNBOOK sections only.
4. Delete the `proto` search path and the `SEARCH_ENGINE` flag in a final separate commit, once config P is recorded.

**Check:** `make prod-up` is healthy locally, CI is green, and the security checklist is complete.

---

## 7. Phase report format (the agent posts this after each phase)

```markdown
## M<n> report
- Done: <bullets>
- Kept from prototype: <bullets>
- Removed or renamed: <item, reason, replacement>
- Check output: <pasted>
- Numbers added to RESULTS: <list>
- Decisions needed: <list or "none">
- Notion cards to move to Review: #..
```

## 8. Definition of done for the migration

- [ ] Every row in the audit gap table is Done or has a written waiver.
- [ ] The prototype's best parts from the keep list are still in the product.
- [ ] Config P (old prototype search) is graded next to A to L, so the report shows the before and after.
- [ ] No second database engine and no external vector store remain.
- [ ] All tests and CI are green; the docs follow the style rule.
- [ ] The Notion cards covered by the migration are in Review, and the human-only cards are left to humans.
