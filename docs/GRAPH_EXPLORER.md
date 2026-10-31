# Graph explorer (C12)

`/graph?article=<id>[&search=<encoded search>&sources=<ids>]` (built by C11's `graphHrefFromSearch`) is a read-only React Flow view of the Neo4j projection ([GRAPH.md](GRAPH.md)). It calls only the C09 routes: `/graph/neighborhood`, `/graph/path`, `/graph/status`, `/articles/{id}` for evidence, and `/search` (retrieval only, never `/answer`) for highlighting.

| Piece | File |
|---|---|
| Merge, caps, deterministic layout, degree, maintenance filter (pure, `npm test`) | `frontend/lib/graph/model.ts` |
| API error → user-facing state | `frontend/lib/graph/errors.ts` |
| State, history, fetches | `frontend/components/graph/GraphExplorer.tsx` |
| Canvas, custom nodes, floating edges | `GraphCanvas.tsx`, `flow-parts.tsx` |
| Inspector, path mode, search highlight, connection list | `Inspector.tsx`, `PathPanel.tsx`, `SearchHighlight.tsx`, `ConnectionList.tsx` |

## Behavior

- **Fetching.** Each exploration or expansion asks for the article's `LINKS_TO` neighborhood (depth 1 or 2, 50 nodes / 100 edges). If Categories is on, it also asks for that article's own categories, one hop. A single combined request fills its leftover node budget with categories in name order, so Wikipedia housekeeping categories (`All articles…`) would always win. "Leave out maintenance categories" removes names that match those housekeeping patterns, a heuristic, until C02 stores the `hidden` flag. Category memberships therefore appear only for the seed and for expanded articles. A missing edge does not mean there is no membership.
- **Caps.** Merges add nodes and edges in API order until the view holds 100 nodes / 200 edges. They add only edges whose two endpoints are both in the view. If the API or the cap drops anything, a "Showing a limited neighborhood" banner appears. Node borders show **connections in this view**, not importance in the corpus.
- **Layout.** The seed sits at the center. The other nodes go on elliptical rings in BFS order, sorted by kind, title, and ID. If two cards would overlap, the later one moves outward along its ray. Expansion never moves an existing node. Each new node takes the first free slot around its parent, facing away from the center of the view. Reset layout recomputes the layout and is added to history. There is no force simulation.
- **History.** Back undoes the last exploration, expansion, path merge, or layout reset (up to 30 steps). Reset returns to the first neighborhood. A response from a different `graph_version` is refused rather than mixed into the view.
- **Path.** Choose the start and end article in the inspector or the path pickers. The path is directed by default; "Ignore link direction" turns on the labelled undirected mode. The list states each link's real direction. "No path within 3 links" comes with a note that it does not mean the articles are unrelated. Path articles that are not in view are added next to their predecessor in the path.
- **Keyboard.** Canvas nodes are not tab stops. The **Connection list** view lists every visible node and the selected node's outgoing links, incoming links, categories, and members. The inspector, path pickers, and toolbar are ordinary buttons and selects.
- **Search context.** Arriving from Search shows "Back to search results". The articles in `sources` get badges straight away. The explorer then re-runs that same retrieval, with the same method, filters and k=5, to load the passages, so the ranks match the Search page. If that fails, the carried articles stay badged in their order.
- **States.** The view handles stale or rebuilding projections (409), Neo4j outage (503), timeouts (504, the graph is kept), unknown articles (404), an unreachable API, a seed with no links, and a revision that differs between Neo4j and MariaDB. The server page shows `/graph/status` first.

## Checks run (2026-10-31)

- `npm test` (`node --test`, 12 tests): a dense, cyclic graph of 100 nodes / 200 edges lays out without overlaps; the layout does not depend on response order; disconnected seed; stable positions on expansion; cap enforcement and truncation; version mismatch; path merge; degree in view; maintenance heuristic; error mapping.
- `npm run lint`, `npm run typecheck`, `npm run build`: pass.
- Browser journey (Playwright 1.64.1, headless Chromium, real API and data `corpus:2`, seed *Convolutional neural network*, keyword query "vanishing gradient" (run before the C11 merge, through the former `q`/`method` link)). Script and screenshots are in `.context/c12/` (not tracked).

### Measured interaction on the demo machine

Apple M6, 24 GB, macOS 27.0, `next dev` (development build), headless Chromium at 1440×1000. Frame figures come from `requestAnimationFrame` during each action. They are observations, not a frame-rate guarantee.

| Action | Result |
|---|---|
| Initial load → first neighborhood rendered | 280–425 ms (45 nodes, 103 edges) |
| One expansion, click → new nodes rendered | 58–96 ms, longest frame 17 ms |
| View at the cap | 100 nodes / 200 edges reached after 7 expansions; banner shown |
| Wheel zoom ×10 at the cap | 51 frames in 852 ms, longest frame 17 ms |
| Drag pan at the cap | 23 frames in 388 ms, longest frame 33 ms |
| Fit view at the cap | longest frame 17 ms |
| Existing node positions after expansion | unchanged (`transform` compared) |
| 390 px mobile | no horizontal page overflow; minimap hidden; details panel stacked below the canvas |

### Not exercised against a real failing service

- **Neo4j outage:** real. A second API instance with `NEO4J_URI` pointing at a closed port served the graph calls and returned `503 graph_unavailable`.
- **Stale projection (409) and timeout (504):** simulated. The browser received the documented error bodies, because making the shared Neo4j stale or slow would have disrupted other work. The API-side behavior is covered by C09's `tests/test_api.py`.
