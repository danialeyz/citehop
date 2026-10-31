# CiteHop visual product specification

Current scope for C10–C13 in COURSE_TASKS.md. Next.js + React + TypeScript + Tailwind replace the old Streamlit plan. Existing paper mockups are visual references only. The interactive knowledge graph is a core feature.

## Visual language

Create a cohesive research workspace with deep navy background, layered dark panels, cyan accents, warm amber category nodes, strong typography, subtle borders, and generous spacing. Reuse the existing hop logo and dark tokens from DESIGN_SYSTEM.md. Centralize tokens/components; avoid a separate theme for each screen. Use crisp icons and text labels, restrained motion, visible focus, and reduced-motion support. No decorative fake metrics or floating elements that obscure data.

Desktop: sidebar navigation, compact status/header, spacious main workspace. Mobile: collapsible navigation and stacked panels; no page-level horizontal scrolling at 390 px. Display SQL/model details only in optional explanatory panels. The main experience should communicate questions, answers, sources, and connections.

## Four routes

| Route | Experience | Source |
|---|---|---|
| `/` | “Ask a question. Follow the sources.” Search hero; after retrieval, prominent answer card and ranked evidence. | FastAPI search/answer; reviewed dev questions. |
| `/library` | Searchable article cards/table, 20 per page; detail with source metadata, stored passages, categories, and Explore connections. | FastAPI article routes. |
| `/graph` | Interactive, read-only knowledge graph with seed search, navigation controls, selected-node inspector, and path mode. | FastAPI Neo4j projection endpoints; MariaDB detail endpoint. |
| `/dashboard` | Corpus overview, graph status, retrieval comparison, timing, grounding review, and downloadable evidence. | Live stats and identified saved evaluation runs. |

Navigation preserves useful query/filter/selected-article state. Graph deep links include seed article and optional search context, never credentials or arbitrary Cypher.

## Search and answers

Large query input, Keyword/Meaning selector, collapsible category/length/linked-from filters, and sample reviewed dev questions. “Find sources” retrieves only. “Generate answer” is explicit and disabled while pending; no paid call on render, sample click, or navigation.

Each source card shows rank, title, passage excerpt, method label, source link, Inspect passage, and Explore connections. Citation labels in the answer open the exact source passage. An answer's citations and generation status are visually distinct from search scores. No invented confidence percentage.

Ignore obsolete responses when the user changes the query; clear stale answers on filter/method changes. Preserve sources when generation fails. Implement loading skeletons, no hits, missing embeddings, insufficient evidence, and service failures with useful recovery actions.

## Knowledge graph: flagship view

Use React Flow with custom nodes and a deterministic radial layout. Build this as an interactive exploration surface, not a screenshot or an editor.

**Canvas:** a restrained grid, pan/zoom, fit view, zoom controls, minimap on desktop, visible node/edge counts, depth selector (1–2), edge-type toggles, category visibility, reset, and selection breadcrumbs. Disable edge creation/deletion. Keep controls usable without hovering.

**Nodes:** article cards with title, article icon, and compact category information. Category nodes use a different shape/icon and amber accent. Seed and retrieved-source nodes have labeled rings/badges. Node size may encode a clearly named degree measure from the API; if only visible degree is available, label it “connections in this view.” Do not imply global importance from a truncated sample.

**Edges:** directional article links with arrowheads; distinct category membership styling. Show relation labels on selection/hover, not across every edge at once. Highlight the selected node's neighborhood and dim unrelated elements. Animated accents, if used, apply only to a selected path and respect reduced motion.

**Inspection:** clicking a node opens a side panel with title, original URL, revision/category metadata, a real stored passage preview, and explicit Expand / Open article actions. Edge inspection states the relationship, source/target, and snapshot provenance. A link is not evidence that two articles agree.

**Expansion:** fetch one bounded neighborhood on demand. Keep existing positions stable; place added nodes around their parent, resolve overlaps deterministically, and offer Reset layout. Do not run a force simulation on every render. Default 50 nodes/100 edges; hard cap 100/200 across the visible graph, with “Showing a limited neighborhood” and truncation indicators.

**Path mode:** select two articles and highlight a backend-computed path of at most three article-link hops. Display a readable sequence with edge directions and links. “No path within 3 links” is an honest result. Exclude category shortcuts. Switching paths must not discard the current search evidence.

**Mobile:** full-width canvas with reachable touch controls, then a collapsible details panel below it. Offer a connection-list mode when the canvas is inconvenient. All selection, expansion, and path actions have keyboard-operable controls/list equivalents.

**Integrity:** graph data comes from Neo4j through FastAPI, source text from MariaDB. Show stale/rebuilding/unavailable states and the import version. Never invent edges to fill space. Graph outage leaves Search and Library usable. Truncated layouts, disconnected seeds, long titles, dense neighborhoods, and empty graphs have deliberate states.

## Dashboard

Four corpus cards: articles, chunks, embedding coverage, loaded article links. Coverage is embedded / total chunks; zero total says “No chunks.” Graph panel shows Neo4j status, article/category/edge counts, imported corpus version, and last import time. A service status is not an invented uptime percentage.

Saved-run section has explicit run/split, corpus/config version, question count, Recall@5 bars, median/p95 retrieval latency, underlying comparison table, and CSV download. Keep query embedding and generation time separate. Show grounding counts with human review status and denominators. Missing values say “Not measured” or “Not reviewed.” Do not combine incompatible runs or imply that a saved benchmark describes a changed live corpus.

## Acceptance evidence

Check all four routes at 1440 px and 390 px, keyboard-only navigation, readable contrast, long content, and reduced motion. Save real-data screenshots under `.context/`; copy selected evidence into tracked docs for submission. Capture the Graph view with a selected node and highlighted path.

Run the main browser journey: search → generate → inspect citation → explore article → select/expand node → inspect path → dashboard. Test graph cap enforcement, version mismatch, timeout, no-path, and Neo4j outage. Record render/interaction observations at the 100-node/200-edge cap on the demo machine and fix visible freezes/overlaps. Do not promise an unmeasured frame rate.
