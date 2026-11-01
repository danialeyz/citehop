# CiteHop migration agent prompts (M1 to M8)

These prompts move the repo from the Wikipedia + Neo4j prototype to the LitSearch target in `MIGRATION_HANDOFF.md`. They replace the C and S prompts in [AGENT_PROMPTS.md](AGENT_PROMPTS.md) for new work. Do not mix the two sets.

How to use:
- Run one prompt per session, in order. Copy one block. Each prompt allows one phase or part only, and no delegation.
- M3 and M6 have human steps in the middle, so they are split into parts (M3a and M3b, M6a to M6c). Each part ends with its own commit and PR. The Human step goes under "Decisions needed" in its report. The next part starts only after that step is done, and it checks the result before it does any work.
- Every session needs `MIGRATION_HANDOFF.md`, `CITEHOP_BOOTSTRAP.md` and [MIGRATION_AUDIT.md](MIGRATION_AUDIT.md) in the checkout.
- The prompts assume the recommendations in audit section 3.3 are approved. If you changed one, edit the matching prompt first.
- Human-only steps are marked **Human**. The agent prepares them and stops.

Open decisions from the audit that must be closed before M1:
1. `CITEHOP_BOOTSTRAP.md` is committed in the repo root.
2. The PR target is chosen (`migrate/citehop` or `master`). Replace `<PR_TARGET>` below.
3. Audit section 3.3 is approved or edited.

## M1: Platform alignment

Prerequisites: M0 audit approved. Cards #2, #6.

```text
Do phase M1 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 6 and 7), CITEHOP_BOOTSTRAP.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: the repo already has docker/docker-compose.yml (mariadb:11.8.9 and neo4j), a Makefile, pyproject.toml with uv locks, .env.example, .editorconfig, .gitignore, citehop/db.py, citehop/apply_sql.py and citehop/check.py. Merge bootstrap files into these. Do not overwrite them.

Steps:
1. Add docker/my.cnf from the bootstrap (mhnsw_max_cache_size=1G, innodb_ft_min_token_size=2) and mount it in compose. Keep Neo4j in compose until M8.
2. Add the bootstrap Makefile targets (schema, kg-schema, test-db, inspect and the rest) next to the existing ones. Keep existing targets working. Keep uv and the lock files; regenerate requirements*.txt only with make locks.
3. Compare citehop/db.py, apply_sql.py and check.py with the bootstrap. Adapt names and behavior, do not rewrite. `make check` must print OK and 11.8.9.
4. Add CI from bootstrap 4.21: a MariaDB 11.8.9 service, schema applied twice, unit and db tests. Add a second job for frontend lint, typecheck and build.
5. Add a root CLAUDE.md and stubs for docs/DECISIONS.md, EXPERIMENTS.md, RESULTS.md, TRAPS.md, GLOSSARY.md and CONTRIBUTING.md. Move the HNSW WHERE-filter trap from docs/RETRIEVAL.md into TRAPS.md (keep a link in RETRIEVAL.md).

Check: make lint && make test pass. make db-up && make check prints OK ... 11.8.9. The prototype still runs: make api, make frontend, one search from the UI. The token-size change needs the FULLTEXT index rebuilt; say how you did it, and do not delete the data volume without asking.

Stop if: a check fails twice, or a pinned version would change. Commit once as "migrate M1: platform alignment", open a PR into <PR_TARGET>, post the handoff section 7 report, and stop.
```

## M2: Schema

Prerequisites: M1. Cards #8, #12.5.

```text
Do phase M2 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.2, 6 and 7), CITEHOP_BOOTSTRAP.md (4.9 and 4.10), and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: the prototype tables are corpus_versions, articles, article_categories, article_links, chunks and embedding_configs in sql/corpus_schema.sql. The audit found no name clash with the target tables, so no proto_ renames are needed. Leave sql/corpus_schema.sql unchanged; it is legacy and goes away in M8.

Steps:
1. Add sql/schema.sql and sql/kg_schema.sql exactly as in the bootstrap: papers, citations, emb_bge_base, queries, qrels, runs, authors, paper_authors, venues, concepts, concept_aliases, paper_concepts, view kg_links, search_log.
2. No vector index in either schema file (rule 10). Indexes are added after load in M3.
3. Add tests/test_schema.py from the bootstrap. Mark db tests with the db marker.
4. Update docs/DATA_MODEL.md: new tables first, prototype tables in a "Legacy (until M8)" section.

Check: make schema kg-schema passes twice in a row. make test-db passes. The prototype tables and data are untouched (row counts before and after match). The prototype UI still searches.

Stop if: any prototype table would need to be dropped or renamed. List it and ask. Commit once as "migrate M2: schema", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M3a: LitSearch data and the Colab notebook

Prerequisites: M2. Cards #9, #10, #12, #13.

```text
Do phase M3, part a (steps 1 to 3), from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.3, 6 and 7), CITEHOP_BOOTSTRAP.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: citehop/acquire.py has a pin-and-verify download cache, citehop/corpus.py a batched loader, and citehop/embed.py a pinned BGE embedder (BAAI/bge-base-en-v1.5, revision a5beb1e3e68b9ab74eb54cfd186867f64f240e1a, CLS pooling, L2 norm). Reuse these patterns. Embed one vector per paper (title + abstract); do not chunk LitSearch.

Steps:
1. Run make inspect and write data/NOTES.md with the exact LitSearch field names and counts. Never guess field names (rule 12); every later script reads them from NOTES.
2. Write load_corpus.py: papers, in-corpus citations, n_cited_by. Write load_questions.py: queries and qrels with kind, origin, and a stratified 20/80 dev/test split with seed 42. Run both.
3. Create the Colab notebook in notebooks/. It must use the same model revision and input format as citehop/embed.py, and write an ids .npy and a float32 vectors .npy plus a checksum file. Write the exact file names and the target folder under data/ in data/NOTES.md, so M3b can find them.

Check: 64,183 papers and 597 queries loaded. Every qrel points at a loaded paper. The dev/test split is stratified and reproducible from seed 42. The notebook runs top to bottom on a 100-paper sample on CPU and its output passes the checksum. make test-db passes.

Stop if: the counts do not match, embedding needs a paid GPU or API, or a check fails twice. Commit once as "migrate M3a: LitSearch data and Colab notebook", open a PR into <PR_TARGET>, and post the section 7 report. Under "Decisions needed", list the Human step: run the notebook on the free Colab tier and put the files where data/NOTES.md says. Stop.
```

## M3b: Vectors and the cosine index

Prerequisites: M3a merged, and the Human Colab run done (the .npy files and checksum exist where data/NOTES.md says). Cards #14, #15.

```text
Do phase M3, part b (steps 4 and 5), from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.3, 6 and 7), CITEHOP_BOOTSTRAP.md, docs/MIGRATION_AUDIT.md and data/NOTES.md first. Follow handoff section 2 at all times.

Context: M3a loaded papers, citations, queries and qrels and added the Colab notebook. Check that before you start: the row counts are 64,183 papers and 597 queries, and the .npy files listed in data/NOTES.md exist and match their checksum. If either fails, stop and report; do not re-run M3a work.

Steps:
4. Write load_vectors.py: id set equals the papers table, length check (768), finite check, bind np.asarray(v, dtype="<f4").tobytes(), bulk load into emb_bge_base, then ALTER TABLE ... ADD VECTOR INDEX vx_emb (emb) DISTANCE=cosine as the last step. No other index after it (rule 10).
5. Keep the Wikipedia data loaded in its own tables. The audit's other-model rule (section 5) does not apply: the prototype uses the same model.

Check: emb_bge_base has 64,183 rows. Query vectors from citehop/embed.py match the notebook vectors for 5 sample papers (cosine above 0.999). A paper's own title as a query returns it at rank 1 for a sample of 20 papers. EXPLAIN of the vector query shows vx_emb. make test-db passes.

Stop if: the vectors do not match the local embedder, or a check fails twice. Commit once as "migrate M3b: vectors and cosine index", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M4: Search in SQL

Prerequisites: M3. Cards #16, #17, #18, #22, #23, #24.

```text
Do phase M4 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.4, 6 and 7), the SQL in the design page section 05, CITEHOP_BOOTSTRAP.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: citehop/search.py holds the prototype chunk search (keyword, vector, exact, hybrid). Its RRF is Python (rrf at citehop/search.py:72). citehop/graph_retrieval.py (S02) expands 1 hop in Neo4j and reranks with cosine + 0.1 * support / seeds, with a safe fallback to the seeds. Do not edit the prototype path; build the new one beside it.

Steps:
1. Write one SQL file per step in sql/: keyword top 100 (MATCH ... AGAINST natural language), vector top 100 (exact shape ORDER BY VEC_DISTANCE_COSINE(emb, ?) LIMIT k, 1 - d computed outside), RRF fusion with UNION ALL + GROUP BY giving top 10 seeds, citation expansion as a recursive CTE (both directions, 1 to 2 hops, weighted by seed similarity, halved per hop, divided by LOG(2 + n_cited_by), with a depth limit), shared references and cited-together self-joins, and the weighted rerank with every term scaled 0 to 1.
2. Add matching functions in citehop/search.py ending in search.fused(). Load SQL from the files; no SQL built with f-strings (rule 15). Bind vectors as <f4 bytes. Every result carries found_via.
3. Add SEARCH_ENGINE=citehop|proto. The API /search uses it. proto keeps today's behavior.
4. Port S02 seed support as one graph rerank term, not a parallel path. Keep the Python rrf only as a test oracle for the SQL fusion.
5. Add fixture db tests for the CTE (hop limit, halving, popularity divisor) and the rerank. Keep weights at untuned defaults; tuning is M7.

Check: EXPLAIN shows the FULLTEXT index and vx_emb. SQL RRF matches Python rrf on fixtures. The CTE and rerank fixture tests pass. The UI returns results with SEARCH_ENGINE=citehop and still works with proto.

Stop if: a check fails twice. Commit once as "migrate M4: search in SQL", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M5: Evaluation

Prerequisites: M4. Cards #19, #20, #21.

```text
Do phase M5 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.5, 6 and 7), CITEHOP_BOOTSTRAP.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: citehop/evaluate.py has article-level Recall@5, latency with warm-up and timing boundaries, and run manifests (git commit, dirty flag, hardware). tests/test_evaluate.py hand-scores metrics. Reuse these. Use dev only in this phase (rule 13).

Steps:
1. Add metrics.py (Recall@5 for specific, Recall@20 for broad, nDCG@10, MRR) with hand-scored tests, and sql/grade.sql computing the same numbers from runs + qrels.
2. Add evaluate.py for the new path: fills runs (config, query_id, rnk, score, found_via) and prints the metrics. Python and SQL numbers must agree. Keep writing a JSON manifest next to it.
3. Define config P as the prototype S01 recipe over the new tables: FULLTEXT top 50 + HNSW top 50, Python RRF k=60, no graph. Grade P, A, B and C on dev.
4. Add the SciFact sanity check (download, embed with the same model, nDCG@10). Target is near 74.04.
5. Add the index sweep: exact vs HNSW over mhnsw_ef_search and M on dev. Choose the cheapest setting with recall at least 0.95 against exact, and record it in docs/DECISIONS.md.
6. Put the dev numbers in docs/RESULTS.md with run IDs.

Check: dev numbers exist for P, A, B and C. SQL and Python agree. SciFact nDCG@10 is within 5 points of 74.04. The index setting is in DECISIONS.

Stop if: SciFact is more than 5 points off. Debug, report, and do not go on. Never touch the test split. Commit once as "migrate M5: evaluation", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M6a: Enrichment, gold set templates and extraction cost

Prerequisites: M5. S2_API_KEY in .env. Cards #12.7, #13.5, #14.5.

```text
Do phase M6, part a, from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.3 L5 and L6, 6 and 7), CITEHOP_BOOTSTRAP.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: citehop/rag.py shows how the repo treats retrieved text as untrusted (escaped, fenced, label check). Use the same approach for extraction prompts.

Steps:
1. Enrichment: authors, venues and years from Semantic Scholar into authors, paper_authors and venues. It needs S2_API_KEY in .env. If it is missing, stop and ask. Respect rate limits and cache responses under data/.
2. Gold set: pick 50 abstracts from the dev split with a fixed seed, and write the labelling templates and the agreement script. Put the template paths in docs/EXPERIMENTS.md.
3. Extraction: write the LLM extraction with quote verification (each concept must quote the abstract exactly). Run it on 100 dev abstracts only if that run is free; otherwise estimate tokens and cost from the prompt and abstract lengths. Write the full-corpus cost estimate to docs/EXPERIMENTS.md. Also propose a pass bar for the gold-set scores (minimum precision and maximum quote-rejection rate) there. Make no paid call.

Check: author, venue and year coverage is in docs/RESULTS.md. The templates and agreement script exist and the script passes on a toy example. The extraction code has unit tests with a fake model, including a rejected made-up quote. The cost estimate is written down.

Stop if: S2_API_KEY is missing, any step would cost money, or a check fails twice. Commit once as "migrate M6a: enrichment, gold templates, cost estimate", open a PR into <PR_TARGET>, and post the section 7 report. Under "Decisions needed", list two Human steps: two people label the 50 gold abstracts, and someone approves the cost estimate and the pass bar (or names a budget, a model and a bar). Stop.
```

## M6b: Extraction run and merge candidates

Prerequisites: M6a merged. Both gold label files filled in. Cost and pass bar approval written in docs/DECISIONS.md (amount, model and bar). Cards #14.5, #15.5.

```text
Do phase M6, part b, from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.3 L6, 6 and 7), docs/MIGRATION_AUDIT.md, docs/EXPERIMENTS.md and docs/DECISIONS.md first. Follow handoff section 2 at all times.

Context: M6a added enrichment, the gold templates, the agreement script and the extraction code. Check before you start: both gold label files are complete, and DECISIONS records an approved budget and model. If either is missing, stop and report.

Steps:
1. Run the agreement script on the gold labels. Record agreement in docs/RESULTS.md.
2. Score the extraction against the gold set. Record precision, recall and quote-rejection rate in RESULTS.
3. Run extraction on the whole corpus within the approved budget. Track spend as you go and stop at 90% of the budget. Cache raw responses under data/ so nothing is paid for twice. Keep only quote-verified concepts.
4. Build merge candidates (aliases and embedding similarity, with bge-base vectors for concepts.emb) into a review file. Do not load concepts or merges yet.

Check: gold agreement and extraction scores are in RESULTS. Spend is recorded and within budget. The review file exists and its path is in docs/EXPERIMENTS.md.

Stop if: spend would pass the budget, extraction scores below the approved pass bar, or a check fails twice. Commit once as "migrate M6b: extraction and merge candidates", open a PR into <PR_TARGET>, and post the section 7 report. Under "Decisions needed", list the Human step: review the merge file. Stop.
```

## M6c: Load concepts and configs K and L

Prerequisites: M6b merged, and the merge review file marked as reviewed. Cards #15.5, #23.5, #23.6.

```text
Do phase M6, part c, from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.3 L6, 4.4 S6, 6 and 7), docs/MIGRATION_AUDIT.md and docs/EXPERIMENTS.md first. Follow handoff section 2 at all times.

Context: M6b produced quote-verified concepts and a merge review file. Check before you start: every row in the review file has a decision. If not, stop and report.

Steps:
1. Load concepts, concept_aliases and paper_concepts (with evidence quotes), using only approved merges. Compute df.
2. Add config K (concept expansion, IDF-weighted) and config L (author expansion) as SQL in sql/ and in citehop/search.py, with depth limits and fixture tests.
3. Put concept coverage in docs/RESULTS.md. Run K and L on dev only.

Check: every paper_concepts row has a verified quote. Concept and author coverage are in RESULTS. K and L run on dev. make test-db passes.

Stop if: a check fails twice. Commit once as "migrate M6c: concepts and configs K and L", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M7: Experiments

Prerequisites: M6. Cards #25, #26, #27.

```text
Do phase M7 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.5, 6 and 7), docs/RESULTS.md, docs/DECISIONS.md, and docs/MIGRATION_AUDIT.md first. Follow handoff section 2 at all times.

Context: citehop/chunk_experiment.py (S03) has a freeze guard: the choice is frozen on dev, and the test run refuses to start before the freeze or a second time. Reuse that guard.

Steps:
1. Tune the rerank weights on dev only. Write the rule before tuning. Freeze the weights in a decision file and in docs/DECISIONS.md.
2. Run configs A to L and P on test once.
3. Compute paired bootstrap intervals for each config against C.
4. Measure latency p50 and p95 per config with the existing warm-up and timing rules.
5. Write results/main_table.csv and update docs/RESULTS.md and docs/EXPERIMENTS.md.

Check: results/main_table.csv has every config with all four metrics, intervals and latency. RESULTS and DECISIONS are updated. Only one test run exists per config.

Stop if: you want to change anything after seeing test numbers. Record it as a limit in RESULTS instead. Commit once as "migrate M7: experiments", open a PR into <PR_TARGET>, post the section 7 report, and stop.
```

## M8: Product and production

Prerequisites: M7. Cards #28, #28.5, #32 to #43.

```text
Do phase M8 from MIGRATION_HANDOFF.md. Read MIGRATION_HANDOFF.md (sections 2, 4.6, 5, 6, 7 and 8), CITEHOP_BOOTSTRAP.md, docs/MIGRATION_AUDIT.md (keep list and planned removals), docs/ARCHITECTURE.md, docs/design/COURSE_UI.md and frontend/AGENTS.md first. Follow handoff section 2 at all times.

Context: keep the Next.js frontend, the Graph Explorer UI (frontend/components/graph, frontend/lib/graph/model.ts) and the FastAPI app under /api/v1. Only their data sources change. Answer generation stays as an optional, ungraded mode.

Steps, each its own commit:
1. API: add /api/v1/paper/{id} and /api/v1/graph/{id} (2-hop subgraph over kg_links, node cap, path). Keep /health and /search. Validate all inputs. Add an env-selected fake embedder for CI. Regenerate frontend types with make api-types.
2. UI: paper cards with found_via tags and the citation path on Search. Point the Graph Explorer at /graph/{id}, with paper, author, concept and venue nodes and a read-only SQL panel that shows the query used. Check 1440 and 390 px; save screenshots under .context/.
3. DB access: read-only DB user for the API, a connection pool, max_statement_time. search_log (hash only, never the raw query) and JSON logs.
4. Production: containers for db, api, app and caddy, model baked into the api image, non-root users. Snapshot, nightly backup and a restore drill with golden queries. Load test with a written budget. Security checklist and CI checks.
5. Deploy (#39) and release (#43) are Human tasks. Write the scripts and RUNBOOK sections only. Do not deploy.
6. Removals, each in its own commit and listed in the report with reason and replacement: the Neo4j service, citehop/graph/, tests/test_graph_neo4j.py and make graph-* (replaced by kg_links CTEs); the SEARCH_ENGINE flag and the proto path (only after config P is in RESULTS); the Wikipedia tables and loaders unless the human kept them as a demo.
7. Rewrite README.md and docs/ARCHITECTURE.md for the final system. No em dashes.

Check: make prod-up is healthy locally. CI is green. The security checklist is complete. The handoff section 8 checklist is filled in.

Stop if: a removal would drop data that is not listed in the audit, before any deploy or paid step, or when a check fails twice. Open a PR into <PR_TARGET>, post the section 7 report, and stop.
```
