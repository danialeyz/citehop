# Design system

## Direction: scientific observatory · approved direction, handoff 1.0

A dark research console with an explicit retrieval protocol, a topology viewport and inspectable evidence. Graphite surfaces establish depth. Cyan marks the active query path. Violet separates semantic retrieval from citation and concept signals. Monospaced labels, numbered phases and fine grid lines communicate scientific structure. Keep the screen readable and avoid decorative metrics. The prior warm editorial direction is superseded.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| paper | #090F1C | Workspace background |
| surface | #111C2E | Cards and inputs |
| ink | #E4EDF8 | Headings and primary text |
| muted | #98ABC3 | Secondary text |
| sidebar | #0C1525 | Persistent navigation |
| teal | #78E4F1 | Main action and selected graph path |
| active | #78E4F1 | Active navigation and logo |
| line | #273950 | Dividers and surface outlines |
| warning | #FFBB75 | Focus outline and error accents |
| keyword | #87E1F0 on #17384A | Keyword chip |
| meaning | #C5B1FF on #2A2446 | Meaning chip |
| citation | #81E7CD on #153B37 | Citation chip |
| concept | #F2CA84 on #3B3023 | Concept chip |
| author | #96BBFF on #1E2F51 | Author chip |

Always pair color with text, icon or shape. Status must never depend on color alone. Validate rendered contrast at implementation time, including disabled and hover states.

## Type

No font download is needed. Use Arial/Helvetica/sans-serif for interface text, the same sans-serif for the cyan landing accent and monospace for evidence quotes, monospace for compact labels. Avoid adding font dependencies unless the owner approves.

| Role | Desktop | Mobile | Weight / line height |
| --- | --- | --- | --- |
| Landing headline | 57px | 43px | 600 / 1.02 |
| Page title | 38px | 32px | 500 / 1.15 |
| Paper title | 34px | 29px | 500 / 1.15 |
| Section title | 22px | 20px | 500 / 1.3 |
| Result title | 19px | 18px | 500 / 1.3 |
| Abstract | 15px | 15px | 400 / 1.8 |
| Interface body | 14px | 14px | 400 / 1.55 |
| Metadata | 11–12px | 11–12px | 400 / 1.55 |
| Eyebrow | 10px | 10px | monospace / 1.4 |

## Layout

Desktop: fixed 214px sidebar, 68px topbar, 42px horizontal content padding. Main content max-width 1600px. Results use flexible content plus a 290px explanation rail. Graph uses flexible canvas plus 270px inspector. Detail uses flexible abstract plus 300px provenance.

At 1100px: sidebar becomes 180px, content padding 28px, graph inspector moves below canvas. At 760px: navigation becomes a horizontal top strip, content padding 20px, all content rails stack. Metrics remain two columns. Tables scroll within their own container; the page must not scroll horizontally.

Spacing scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px. Card radius 8px, controls 4px, chips 3px. Borders 1px. Card padding 23px desktop and 19px compact. Buttons target at least 44px in production; compact chips are not primary touch actions.

## Components

| Component | Anatomy | Required states |
| --- | --- | --- |
| App shell | Brand, four nav links, context header | Active, focus, mobile strip |
| Search composer | Visible label, query input, submit, method selector | Idle, invalid, loading, disabled |
| Method selector | Keyword / Meaning / Fused / CiteHop | Selected, keyboard focus, unavailable |
| Paper result | Rank, title, authors, year, chips, snippet, explanation link | Standard, graph-only, incomplete metadata |
| Evidence card | Concept, kind, relation, exact abstract quote | Available, absent, low confidence if supplied |
| Provenance card | found_via, graph path, final score, contributions | Present, unknown, not applicable |
| Graph | Directed edges, labeled nodes, inspector, text alternative | Loading, selected node, empty, capped, error |
| Metric card | Name, value, eligible question set | Not run, loading, measured, failed |
| Ablation row | Letter, definition, metrics, status | Pending, running, measured, failed, reference |
| Banner | Plain-language state plus next action | Informational, error, stale, partial |

## Motion and accessibility

Use 120–180ms transitions for color or selection. No continuous force simulation after the layout settles. Disable motion under prefers-reduced-motion. The prototype has a static graph and reduced-motion support.

Provide a skip link, semantic landmarks, one h1, visible labels, visible focus, aria-pressed on method buttons and aria-current for navigation. Announce completed searches with a polite status message. Do not announce every result. On route changes, move focus to the main region. Restore focus to the originating result when returning from detail in production.

The graph must have a keyboard-accessible list of nodes and a textual edge list. Do not require dragging to inspect evidence. On mobile, use the readable connection list when graph labels become too dense. Support 200% zoom without losing controls.

## Assets

The original logo is a three-node connected mark. SVG is the editable master. The mark uses cyan nodes on graphite. Only direct browser screenshots from the canonical HTML can become current visual references. Old print boards are superseded. No stock photos, generated illustrations or third-party assets are required.

## Scientific visual structure

- Landing: a large two-line research headline beside an instrument-like topology viewport. The graph has radial guides and a subtle coordinate grid. These are presentation guides, not measured axes.
- Retrieval strip: four compact modules for MariaDB full-text, 768-dimensional BGE, bounded graph walks and rank fusion. All describe the documented architecture.
- Results: a query → retrieve → fuse → expand → rerank sequence establishes process. Rank badges and signal chips make evidence scannable.
- Graph: cyan seed, cyan/teal paper neighbors, amber concepts and blue authors. Dashed radial guides do not indicate similarity or distance.
- Evaluation: monospaced metrics, a distinct reference row and per-metric color accents. Empty values remain empty.
- Surfaces: graphite canvas, raised navy panels and thin blue-gray boundaries. Avoid bright backgrounds or lime accents from revision 0.1.

The CSS file retains the original structural styles, followed by a labeled V0.2 override block. The last matching rule is authoritative. A production implementation should consolidate the final tokens when implementing the approved design.
