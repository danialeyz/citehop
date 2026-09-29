# Screens and behavior

## Navigation and state

Prototype routes are hashes in `prototype/index.html`. Production may map these to Streamlit pages or session state. Preserve query, mode, selected paper and scroll position across navigation. Use stable paper IDs, not list indexes, outside the fixture.

| Route | Screen | Main action | Secondary action |
| --- | --- | --- | --- |
| #search | Search landing | Submit question | Try sample question |
| #results | Ranked results | Open paper | Open graph |
| #paper-0 / #paper-1 / #paper-2 | Paper detail | Inspect connections | Return to results |
| #graph | Graph explorer | Select node | Read connection list |
| #experiments | Evaluation | Select split | Export plan |
| #settings | Development settings | Preview parameters | Reset defaults |
| #loading | Search in flight | Cancel | Preserve input |
| #empty | No results | Refine question | Change method |
| #error | Retrieval failure | Retry | Preserve input |
| #missing | Missing graph links | View paper | Return to results |

## Search landing

Lead with a short question-oriented headline, the query composer and three example questions. The graph illustration establishes the product idea. It is not a claim about corpus topology.

The input has a visible label, a placeholder, a proposed 2,000-character UI limit and Enter-to-submit. Trim whitespace. Reject whitespace-only input with an inline message in production. Do not start retrieval while the user types. Examples prefill and submit an illustrative query. Four method choices map to keyword, vector, fused and citehop. Defaults to CiteHop as a design proposal.

Expected corpus size and benchmark question count are informational. Do not display a “connected” database state unless a real health check confirms it.

## Results

Show the query and mode at the top. The production list contains at most 20 results, in backend rank order. Never resort by a visually convenient score. Each result shows rank, title, author names if supplied, year if present, found_via chips, an abstract excerpt and an explanation link. Text snippets must come from stored content, not generated summaries.

Only apply the special graph-only treatment when provenance proves that the paper is absent from keyword and vector candidate sets for the same query and configuration. Displaying a citation chip alone is insufficient. The evaluation metric also requires that the paper is relevant under qrels.

Show counts and elapsed time only when measured. State whether counts refer to returned results or all matching records. If a retrieval branch fails, display an explicit partial-results banner and list unavailable methods. Never silently label fallback keyword results as full CiteHop results.

## Paper detail

Show full title, available authors, year and venue. Missing values use “Not available” or “Unknown”; do not convert null year to 0 or null abstract to an empty-looking card. Abstract text is plain escaped content. Evidence quotes must be verbatim substrings of the stored abstract.

Concept entries include name, kind, relation and evidence. Confidence may be shown only if supplied, and must be called extraction confidence, not retrieval relevance. Keep the original quote even when aliases are canonicalized. Link the graph from the paper's stable corpusid.

The sidebar shows final score and per-signal contributions only if the service provides them with an explicit definition. The raw score is not a probability. Do not add a percentage ring or confidence meter.

## Graph explorer

The proposed graph starts from one selected paper. A finite hop limit is always required. Node types: paper, author, concept and venue. Venue is in the source schema but is not shown in the small prototype fixture. Use a rounded square or a distinct labeled shape for venue in production.

Preserve relation types: cites, cited_by, wrote, written_by, proposes, uses, evaluates_on, addresses and published_in. Inverse concept links in kg_links reuse the same relation name; retain direction and explain it in the readable edge list. Do not interpret all relations as citations.

Production behavior: click or keyboard-activate a node to open its inspector; show identity, type and related evidence. Pan and zoom may enhance navigation, but a Reset view control and text list must remain available. The prototype only implements node inspection and a depth emphasis preview. It does not implement live traversal, panning, zoom or layout physics.

Proposed rendering cap: 100 nodes and 200 edges per neighborhood. This is a frontend guardrail, not a source requirement. Show “Neighborhood limited” when capped, plus the finite depth and returned count. Never claim the viewport represents the complete knowledge graph.

## Experiments

The screen has a dev/test selector, four metric cards, the A–L table, graph-only discovery, latency and uncertainty information. C is marked as the comparison reference. All definitions and values remain unknown until project cards and actual runs supply them.

Not run is displayed as a dash with a text status. A real zero is displayed as 0.000 or 0.0%, according to the metric. Failed and incomplete runs must not be averaged as zero.

Proposed formatting: Recall as percentages with one decimal; nDCG and MRR as 0–1 values with three decimals; latency in ms; counts as integers. Keep canonical raw values in exports. Provide matching units for deltas and bootstrap intervals. The original handout reports some literature values on a percentage scale, so normalize explicitly before comparing.

On dev: future tuning actions can be enabled after configuration definitions exist. On test: use frozen configurations and read-only results. The current prototype performs neither evaluation nor tuning. Export plan produces A–L rows with unresolved definitions. Production exports must include split, config definition, run identity, query counts, timestamp, model settings and the producing command/SQL.

## Settings

The signature defaults a=.7, b=.2, c=.1, signal=expand, hops=1, weighted=true, damp=true, prior=false are source facts. Their semantic mapping is not supplied. Therefore this design names parameters a/b/c and does not relabel them keyword/meaning/graph.

The prototype proposes numeric 0–1 bounds and a 1–2 hop control. These need backend confirmation. Do not enforce sum-to-one unless the scoring spec requires it. Use a labeled inline validation message when a value is outside the accepted server range. Reset returns to the known defaults. Applying settings must not automatically run a held-out test evaluation.

## State matrix

| Condition | Content | Recovery |
| --- | --- | --- |
| Initial | Headline, examples, empty composer | Enter query |
| Loading | Current question and progress label | Cancel; do not fabricate progress percentage |
| Empty | No papers message, query retained | Refine or choose another method |
| DB unavailable | Plain-language error | Retry with same settings |
| Timeout | Timeout message and completed/partial status | Retry or reduce permitted expansion |
| No abstract | Metadata remains visible | Inspect graph if available |
| No graph links | Empty neighborhood message | View paper |
| No concept evidence | No claimed extraction | Continue with citation or author evidence |
| Partial enrichment | Available fields only | Label missing coverage |
| No experiment runs | Dashes plus Not run | Define configurations first |
| Stale result | Old query/config label | Rerun, never silently mix settings |
| Long title | Wrap naturally | No hidden title-only tooltip dependency |

The four dedicated state routes are visual references. The remaining cases are specified here for implementation acceptance.
