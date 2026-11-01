# Five-minute demo script (C14)

Audience: course reviewers. Goal: show MariaDB doing semantic search and SQL filtering in one statement, a cited answer whose evidence you can open, the Neo4j graph as a separate exploration layer, and the measured results. Every number shown comes from the live databases or from a saved run in `results/runs/`.

## Before the demo (not timed)

```sh
make db-up && make graph-status          # expect "ready" and matching versions
make api                                 # terminal 1
npm --prefix frontend run build && npm --prefix frontend run start   # terminal 2, :3000
ollama ps                                # generator reachable; warm it with one answer
```

Open `http://127.0.0.1:3000`, a terminal with `make db-shell`, and `sql/search_examples.sql` in an editor. Close other heavy apps: Ollama's model alone is about 14 GB.

## Script

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00–0:30 | README | Show the first line and the diagram. | "Area 4: native vector search and RAG. 100 pinned English Wikipedia ML articles, 1,776 chunks with `VECTOR(768)` embeddings in MariaDB 11.8.9. Neo4j is a derived copy of the article links for exploration only." |
| 0:30–1:30 | Search | Type *Who coined the term machine learning, and when?*, keep **Meaning**, press **Find sources**. Then open **Filters**, set a category or *linked from*, and search again. | "Retrieval only: five ranked passages, cosine similarity from `VEC_DISTANCE_COSINE`. The filter is an SQL `EXISTS` predicate in the same statement, evaluated before `LIMIT`, then joined back to `articles`. No Python post-filtering." |
| 1:30–2:15 | SQL shell | `make sql FILE=sql/search_examples.sql` (or paste example 3). Point at the `EXPLAIN` lines. | "Unfiltered queries use the HNSW index `vx_chunks_embedding`. With a predicate, MariaDB 11.8 applies `WHERE` after the index's candidate list, so we deliberately run an exact scan over the eligible rows. That is a measured trade-off, not a hidden one." |
| 2:15–3:00 | Search | Clear filters, search again, press **Generate answer**, then click the **S1** citation. | "One explicit generator call, at most 5 passages and 300 output tokens. The server loads the passages by chunk ID; the browser cannot send its own text. The citation opens the exact stored passage. A valid label is not proof of support, which is why grounding has a separate human review." |
| 3:00–4:00 | Graph | **Explore connections** on the first source. Click a neighbor, **Expand neighborhood**, then choose start/end in **Path between two articles** and **Find path**. | "These are real Wikipedia links and categories imported from MariaDB into Neo4j with an explicit, versioned import. Bounded: one hop by default, 100 nodes / 200 edges max, paths up to 3 links. The snapshot version is shown; a stale graph disables traversal while search keeps working." |
| 4:00–4:45 | Dashboard | Point at live counts, the Neo4j panel, Recall@5 and latency, and the grounding panel. | "Recall@5 on the 20-question test split: 0.976 vector vs 0.959 keyword. Filtered vector search costs more because it is exact. These are provisional: the 30 questions and 10 answers are not human-reviewed yet, and the page says so." |
| 4:45–5:00 | README | Scroll to *What the database-native approach gave us* and *Limitations*. | "Vectors live in the same row and transaction as the text and metadata: one statement, one source of truth. Neo4j costs about 0.6–0.7 GB more memory and an explicit import step." |

## Fallbacks

- Generator slow or down: the answer card shows *Generator unavailable* and keeps the sources; continue with the citation step from an earlier search, or show `results/runs/<id>/answers.json`.
- Neo4j down: say so and show that Search and Library still work (`/api/v1/health` reports `neo4j: unavailable`). Use `docs/screenshots/graph-path-1440.png` for the graph.
- Screenshots of every view are in [`docs/screenshots/`](screenshots/).
