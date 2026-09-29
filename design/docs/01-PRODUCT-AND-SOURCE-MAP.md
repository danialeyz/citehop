# Product and source map

## Product intent

CiteHop is a scientific paper search engine in MariaDB 11.8.9. Its central research question is whether graph links retrieve correct papers that keyword and meaning search miss. The frontend must make retrieval provenance understandable, not merely present a ranked list.

The supplied document is a bootstrap specification. It provides domain facts and backend constraints. It does not provide complete visual specifications, exact A–L definitions, the scoring formula, API endpoints, or the contents of the linked designs. All layout, color, interaction and component choices below are proposals derived from that source.

## Scope

| Surface | Why it exists | Source location |
| --- | --- | --- |
| Search landing | Enter a question and choose retrieval method | §1, §4.16 |
| Search results | Ranked top 20 with multiple retrieval signals | §4.9 runs, §5.3 |
| Paper detail | Read metadata and quoted concept evidence | §4.9 papers, §4.10, §5.5 D-9 |
| Graph explorer | Inspect papers, concepts, authors and typed links | §4.10 kg_links, §5.4, §8 card #28.5 |
| Experiments | Compare A–L, metrics, latency and confidence intervals | §5.6, §5.7 |
| Search settings | Inspect proposed controls for search.citehop parameters | §4.16, §5.5 pending decisions |

No authentication, collaboration, saved library, subscriptions, AI chat, generated paper summaries, PDF hosting or account management is specified. These are not added.

## Requirements traced to UI

| Source requirement | UI treatment | Implementation constraint |
| --- | --- | --- |
| FULLTEXT keyword retrieval | Label “Keyword” and explain “MariaDB full-text” | Never call this BM25 |
| BGE base, 768 dimensions, cosine | Read-only meaning-search metadata | Keep model identity and vector rules |
| RRF, graph expansion, weighted reranking | Four-step explanation beside results | No invented contributions or normalized score |
| found_via SET | Several chips on one result | Preserve kw, vec, cite, concept, author |
| citations and authors | Directed paths and author nodes | Respect citation direction and author IDs |
| LLM-extracted concepts | Concept kind, relation, exact evidence quote | No evidence means no asserted extracted relation |
| Expected 64,183 papers / 597 questions | Landing page labels say “expected” | Replace with verified count only after load |
| Top 20 search output | Results list capped at 20 | Never imply fixture count is live corpus count |
| Tune on dev, report on test | Explicit split selector and test lock semantics | Enforce on server, not only in UI |
| A–L ablation | Twelve unpopulated rows | Do not infer definitions from letters |
| Config C comparison | Reference badge on row C | Meaning of C remains unresolved |
| Recall@5 specific / Recall@20 broad | Metric cards identify relevant question types | Use appropriate denominator and split |
| nDCG@10, MRR | Empty summary cards pending measured runs | Zero and not-run are different values |
| Graph-only relevance | Separate research metric | Requires qrels and candidate sets |
| p50/p95 latency | Separate measurement area | Never fabricate timings |
| 1,000 bootstrap resamples / 95% interval | Evaluation methodology card | Paired comparison against C |
| Demo app (#28) | Next.js + TypeScript + Tailwind in web/ over a Python API | Stack changed from Streamlit on 2026-09-29; see docs/13 |

## Unknowns that must remain explicit

1. A–L configuration definitions. Only the count, letters and comparison against C are known.
2. Signal mapping for a, b and c, and the full weighted score formula.
3. Allowed signal values beyond the signature default `expand`.
4. Final hop count, prefix choice, M and ef_search, extraction model, merge threshold and venue cleaning.
5. LitSearch raw field names. §2 forbids guessing before card #9.
6. Actual load counts, coverage and all experiment results.
7. Provenance path serialization, latency storage and per-signal score storage. These are not in the supplied runs table.
8. Exact external paper URLs. The schema supplies corpusid, not a URL field.
9. A repeated-run identifier. The runs key alone does not distinguish repeated executions.

The supplied headings sometimes say five KG tables. The SQL contains six: authors, paper_authors, venues, concepts, concept_aliases and paper_concepts. Together with the six core tables, the schema has 12 tables plus kg_links. This package follows the actual supplied schema.
