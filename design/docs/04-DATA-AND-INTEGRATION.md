# Data and integration contract

## Architecture boundary

Keep retrieval inside the existing Python and MariaDB project. The prototype does not introduce a second database, vector store or graph service. Browser clients must never receive DB credentials or raw vector bytes.

The source planned `app/streamlit_app.py` for #28. That is superseded: the frontend is Next.js in `web/`, and a Python API in `citehop/api.py` serves these view models (docs/13). Keep search logic in `citehop/search.py`, graph queries in approved SQL/Python modules and evaluation in `citehop/evaluate.py`. Do not embed SQL in layout templates.

The structures below are proposed view models, not claims about existing APIs. An adapter must build them from approved backend results. The handout specifies no HTTP endpoints; docs/13 proposes them. The API serializes these view models as JSON, and TypeScript types are generated from contracts/.

## Search input

| Field | Type | Rule |
| --- | --- | --- |
| query | string | Nonempty after trim; proposed UI maximum 2,000 chars |
| method | keyword / vector / fused / citehop | Map directly to supplied function names |
| parameters | optional object | Use documented defaults only; validate server-side |
| request_id | string | Proposed client request identity to discard stale responses |

`keyword(q, k=100)` and `vector(q, k=100)` are candidate retrieval functions. The UI top-20 limit is not a reason to change their candidate depth to 20. Use the pipeline specified by backend cards.

## Search view model

```typescript
type Via = 'kw' | 'vec' | 'cite' | 'concept' | 'author';
type Paper = {
  corpusid: string; // Serialize BIGINT as decimal string for browser safety.
  title: string;
  abstract: string | null;
  year: number | null;
  n_cited_by: number | null;
  authors: { author_id: string; name: string; position: number }[];
  venue: { venue_id: number; name: string } | null;
};
type Result = {
  paper: Paper;
  rank: number;
  score: number | null;
  found_via: Via[];
  graph_only: boolean | null; // Unknown is distinct from false.
  explanation: {
    score_definition: string | null;
    contributions: Record<string, number> | null;
    paths: GraphPath[] | null;
  };
};
type GraphPath = { nodes: string[]; edges: GraphEdge[] };
type GraphEdge = { source: string; target: string; relation: string };
type SearchView = {
  query: string;
  method: string;
  results: Result[];
  returned_count: number;
  latency_ms: number | null;
  partial: boolean;
  unavailable_methods: string[];
};
```

No scores, contributions, graph_only, timings or paths are to be invented when the backend does not supply them. The supplied runs table stores config, query_id, rnk, corpusid, score and found_via. Other fields require runtime computation or a later approved persistence design.

## Source mapping

| UI field | Source |
| --- | --- |
| Title / abstract / year / citation count | papers |
| Author names and ordering | paper_authors joined to authors, ordered by position |
| Venue | papers.venue_id joined to venues |
| Concept name / kind | paper_concepts joined to concepts |
| Relation / evidence / confidence | paper_concepts |
| Alias resolution | concept_aliases |
| Directed citation | citations.citing_id → citations.cited_id |
| Explorer links | kg_links; node prefixes distinguish type |
| Stored rank / score / labels | runs.rnk / score / found_via |
| Query kind / origin / split | queries |
| Correct-paper membership | qrels |

Graph node IDs use the supplied convention: `paper:<id>`, `author:<id>`, `concept:<id>`, `venue:<id>`. Keep IDs even when labels duplicate. A node label is not a unique identifier.

## Graph view model

Return nodes, directed edges, selected seed, depth_limit and truncated flag. For concepts, return original evidence and extraction confidence when applicable. Node positions may be computed in the UI; they are presentation state, not research output. Cache by seed, finite depth, relation filters and data revision. Avoid unlimited recursive queries on every pan or hover.

## Experiment view model

Each measured run needs a stable identity, config letter and full definition, explicit split, timestamp, eligible query counts, metrics, latency summary, comparison interval and producing command/SQL. These fields are proposed additions to the presentation layer. The schema's runs primary key cannot safely distinguish repeated executions of the same config and query without a separate approved design.

Do not add a history or “rerun” persistence feature by silently changing the schema. Resolve this with the experiment card first. Literature baselines are not project measurements and must be shown separately if added later.

## Error boundary

Present a stable code, safe human message, retryable flag and partial-result flag. Never include database passwords, SQL parameters containing secrets, connection strings or stack traces in user-facing banners. Log detailed failure information server-side. Escape query, title, abstract, author and evidence content before HTML rendering.

## Backend invariants to preserve

- MariaDB remains pinned to 11.8.9.
- Vector index distance is cosine. Vector ORDER BY remains `VEC_DISTANCE_COSINE(col, ?) LIMIT k` with no inline score math.
- Vectors remain checked 768-dimensional little-endian float32 bytes.
- Add vector indexes only after bulk load; do not add another index afterward.
- Every recursive CTE has a finite depth condition in its recursive part.
- Tune only on explicit dev data; test evaluation takes an explicit split.
- Keep all secrets server-side and outside git.
- Do not guess raw LitSearch fields. Card #9 supplies them.
- Do not change bootstrap phases, pinned versions or project checks for styling.
