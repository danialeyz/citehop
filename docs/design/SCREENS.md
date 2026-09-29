# CiteHop screens

One section per route in the prototype. Each lists what the screen shows, how it behaves, and where the real data comes from.
Table and column names match `sql/schema.sql` and `sql/kg_schema.sql`. Function names match the stubs in `citehop/`.

Legend for the **Source** column:

| Mark | Meaning |
|---|---|
| `static` | fixed copy, fine to hard-code |
| `db` | read from MariaDB at runtime |
| `fn` | returned by a `citehop` Python function |
| `open` | not decided yet; see [AGENT_INSTRUCTIONS.md](AGENT_INSTRUCTIONS.md#5-open-decisions) |

## Shell (every screen)

| Element | Content | Source |
|---|---|---|
| Brand | logo + "CiteHop" | static, logo is open (UI-3) |
| Subtitle | "Connected research" (light) / "Research intelligence" (dark) | open (UI-1) |
| Nav | Search papers, Graph explorer, Experiments, Search settings | static |
| Breadcrumb | `Workspace / <page title>` | static per route |
| Status pill | prototype says "Illustrative prototype". Real app: DB state, for example "MariaDB 11.8.9 · connected" | db (`SELECT VERSION()`) |
| Collection | "LitSearch collection" | static |
| Sidebar footer | "A database research project", "Danial & Akshat", "MariaDB 11.8.9 · LitSearch" | static |

The prototype's **Review states** bar and "Design review draft" note are for design review only. Do not ship them.

## 1. Search (`#search`)

Purpose: ask a question.

| Element | Content | Source |
|---|---|---|
| Eyebrow | "Scientific paper discovery" (light) / "Scientific retrieval / connected evidence" (dark) | static |
| Hero h1 | "Follow the evidence. Find the *connection*." (light) / "Research is a graph. Find your next edge." (dark) | open (UI-1) |
| Hero text | "Search beyond matching words. Explore the papers, people, and ideas that connect your research." | static |
| Method tags (dark) | `01 / LEXICAL`, `02 / SEMANTIC`, `03 / GRAPH` | static |
| Hero graph | decorative neighbourhood, not interactive | static SVG |
| Stat strip (dark) | MariaDB full-text · BGE 768 dimensions · Bounded graph walks · RRF → weighted rank | static |
| Search panel | see component; default method CiteHop | |
| Example cards | 01 Citations, 02 Concepts, 03 Authors, each a sample question | static; must not be test-split questions (rule 8) |
| Numbers | papers count, questions count, "One database." | db: `SELECT COUNT(*) FROM papers`, `SELECT COUNT(*) FROM queries` |

Behaviour:
- Submit with an empty input focuses the input and does nothing else.
- Submit or example click goes to Results with the query and the selected method.
- Before data is loaded, the numbers show the expected values with the word "expected" (64,183 and 597), as in the prototype. After loading, show the real counts and drop "expected".

Method to function:

| Segment | Calls | Hint text |
|---|---|---|
| Keyword | `search.keyword(q, k=100)` | Selected method: Keyword |
| Meaning | `search.vector(q, k=100)` | Selected method: Meaning |
| Fused | `search.fused(q)` | Selected method: Fused |
| CiteHop | `search.citehop(q, ...)` with the Settings values | Text + meaning + graph links |

The return shape of these functions is open (UI-4). The UI needs, per result: `rnk`, `corpusid`, `score`, `found_via`.

## 2. Results (`#results`)

Purpose: show the ranked papers and why each one is there.

| Element | Content | Source |
|---|---|---|
| Heading | eyebrow "Search workspace", h1 "Follow your question.", button "Open graph ↗" | static |
| Search panel | compact, pre-filled with the query | state |
| List header | "Relevant papers / N results", "Ranked by <method>" | fn |
| Result rank | `01` to `20` | fn `rnk` |
| Title | `papers.title` | db |
| Meta line | authors · year · venue | db: `paper_authors` ordered by `position` → `authors.name`; `papers.year`; `venues.name` via `papers.venue_id` |
| Chips | one per value in `found_via` | fn |
| Abstract | `papers.abstract`, clamp to about 3 lines | db |
| Footer text | provenance sentence, see below | fn |
| Link | "Why this paper? ↗" to Paper detail | |
| Side card 1 | "Behind the results": 01 Retrieve, 02 Fuse, 03 Explore, 04 Rerank → top 20 | static |
| Side card 2 | research question "What can graph links find that words and meaning miss?" + link to Experiments | static |

Rules:
- At most **20** results.
- A result whose `found_via` has neither `kw` nor `vec` is a **graph-only** find. Give it the highlight style and the eyebrow "A connection beyond text". Footer: "Outside keyword and meaning candidate sets."
- Any other result. Footer: "Found by <n> signals" or similar, derived from `found_via`.
- Missing author, year or venue: omit that part of the meta line. Do not print "null" or "Unknown" there.

## 3. Graph explorer (`#graph`)

Purpose: show the neighbourhood of a paper and the path that led to a result.

| Element | Content | Source |
|---|---|---|
| Heading | eyebrow "Knowledge graph / neighborhood", h1 "Every paper has a neighborhood.", button "Back to results" | static |
| Depth select | 1 hop, 2 hops | UI limit; backend enforces its own limit (rule 9) |
| Legend chips | Paper, Concept, Author | static |
| Canvas | nodes and edges around a seed paper | db: `kg_links` view (exploring), bounded by depth |
| Node detail card | name, type, description, chips, Path length, Edge type, "Inspect paper ↗" | db |
| Readable path | seed → edge label → node → edge label → node | db |
| Accessible list | every visible edge as text: `A → rel → B` | db |

Node types and labels:

| `kg_links` prefix | Node | Glyph | Label source |
|---|---|---|---|
| `paper:` | Paper | `▤` | `papers.title` (shortened) |
| `concept:` | Concept | `◇` | `concepts.name` |
| `author:` | Author | `A` | `authors.name` |
| `venue:` | Venue | not in design | open (UI-5) |

Edge labels come from `kg_links.rel`: `cites`, `cited_by`, `wrote`, `written_by`, `proposes`, `uses`, `evaluates_on`, `addresses`, `published_in`.

Rules:
- Every neighbourhood query has a depth limit in the recursive part and a node cap. Proposed cap: 50 nodes (open, UI-6).
- Label only large nodes on the canvas. All nodes keep their `aria-label`.
- Selecting a node updates the detail card without a page reload.
- The seed is the paper the user came from. With no seed, show the Missing state.

## 4. Paper detail (`#paper-<n>`)

Purpose: everything about one paper and why it was returned.

| Element | Content | Source |
|---|---|---|
| Back link | "← Back to search results" | |
| Eyebrow | "Paper detail" | static |
| Title | `papers.title` | db |
| Meta | authors · year · venue ("Venue not available" when NULL) | db |
| Chips | `found_via` for this query | fn / `runs` |
| Abstract card | `papers.abstract` | db |
| Concept evidence card | per `paper_concepts` row: `concepts.name`, chip `<relation> · <concepts.kind>`, quote = `paper_concepts.evidence` | db |
| Provenance card | "Why this paper?", sentence, Final score, Signal contributions, "Explore connections ↗" | fn |
| Metadata card | Corpus ID = `papers.corpusid`, Citations received = `papers.n_cited_by`, Full text URL | db; URL is open (UI-7) |

Rules:
- The evidence quote must be the exact stored `evidence` text. It is a substring of the abstract (D-9). Never paraphrase it.
- If the score breakdown is not available from the search function, show "Not computed", as the prototype does. Do not invent a split.

## 5. Experiments (`#experiments`)

Purpose: the A to L ablation and its metrics.

| Element | Content | Source |
|---|---|---|
| Heading | eyebrow "Evaluation workspace", h1 "Does the graph make a difference?", button "Export plan ↓" (CSV) | |
| Intro | "Compare 12 configurations against the LitSearch answer key. Tune on development data. Report on held-out test data." | static |
| Split select | Development · tuning / Test · reporting only | state |
| Split note | dev: "Development only · tuning permitted · seed 42"; test: "Reporting only · frozen configurations · no tuning" | static |
| Metric cards | Recall@5 (specific questions), Recall@20 (broad questions), nDCG@10, MRR | db: `runs` join `qrels` join `queries`, filtered by split |
| Ablation table | A to L; CONFIG, DEFINITION, 4 metrics, STATE; C marked "Reference" | db + `docs/EXPERIMENTS.md` for definitions |
| Footer cards | Found only via graph · Latency p50/p95 · Uncertainty (paired bootstrap, 1,000 resamples, 95% interval vs C) | db / `docs/RESULTS.md` |

Rules:
- A metric with no run shows `—` and "no run". Never a placeholder number.
- Config definitions come from `docs/EXPERIMENTS.md`. Until it has them, show "Not defined yet".
- The split is always explicit in every query (rule 8). The Test view has no tuning controls.
- "Found only via graph" = relevant results (in `qrels`) whose `found_via` has no `kw` and no `vec`.

## 6. Search settings (`#settings`)

Purpose: make every search parameter visible before a dev run.

| Element | Content | Source |
|---|---|---|
| Heading | eyebrow "Search settings", h1 "Make every signal explicit." | static |
| Reranking weights | a = 0.7, b = 0.2, c = 0.1, number inputs 0 to 1 step 0.05 | defaults from `search.citehop` signature |
| Graph expansion | Hop limit (1, 2), Weighted links (on), Damping (on), Prior (off) | `hops`, `weighted`, `damp`, `prior` |
| Meaning search | Embedding model bge-base-en-v1.5, Dimensions 768, Distance Cosine | read-only, from `citehop.embed` |
| Research guardrails | tune on dev only; test uses frozen configs | static |
| Actions | "Preview settings", "Reset defaults", status text | |

Rules:
- The weights' signal names are unresolved (open, UI-8). Label them "Parameter a/b/c" until DECISIONS.md names them.
- Settings are session state. The prototype saves nothing; keep it that way unless a card says otherwise.

## 7. States

Each state keeps the compact search panel above it, so the user keeps their question.

| State | Icon | Title | Text | Action |
|---|---|---|---|---|
| loading | `◌` | Following the evidence… | Retrieving candidates, fusing ranks, and checking graph connections. | Cancel search |
| empty | `⌕` | No papers found for this question. | Try fewer terms or switch retrieval methods. Keep your question so you can refine it. | Edit question |
| error | `!` | Search could not finish. | The database or retrieval service is unavailable. Your question and settings are preserved. | Retry search |
| missing | `◇` | No connections available yet. | This paper has no loaded graph links. You can still inspect its metadata and abstract. | View paper |

When each appears:

| State | Trigger |
|---|---|
| loading | a search or graph query is running |
| empty | the search returns 0 rows |
| error | `mariadb.Error` or a model load failure. Log the detail; show only this message. |
| missing | the seed paper has no rows in `citations`, `paper_authors` or `paper_concepts` |
