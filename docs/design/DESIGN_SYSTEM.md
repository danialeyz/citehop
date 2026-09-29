# CiteHop design system

Two themes exist. Light comes from `citehop-preview-v0.1.html` (exact values from its CSS).
Dark comes from `desktop-search-dark.png` (values sampled from pixels, so treat them as close, not exact).
Which theme ships is open decision UI-1 in [AGENT_INSTRUCTIONS.md](AGENT_INSTRUCTIONS.md#5-open-decisions).

## 1. Colour tokens

### Light theme (exact)

| Token | Value | Use |
|---|---|---|
| `--paper` | `#f5f4ef` | page background |
| `--surface` | `#fffefa` | cards, search panel, inputs |
| `--ink` | `#193b38` | main text |
| `--muted` | `#596a65` | secondary text |
| `--line` | `#d9dfd5` | borders, dividers |
| `--teal` | `#115b50` | primary button, links, focus of path, seed node |
| `--lime` | `#d5ed91` | active nav item, logo nodes |
| `--orange` | `#a54829` | focus ring only |
| `--violet` | `#655098` | reserved (meaning) |
| `--blue` | `#346b92` | reserved (author) |
| sidebar bg | `#123c36` | left rail |
| sidebar text | `#c8d8cf` / `#e8eee4` | nav links / brand |
| note bg / border / text | `#eeedde` / `#dedbc7` / `#555a41` | disclaimers |
| highlight row | `#eaf0e0` | the "connection beyond text" result |
| quote bg / border | `#f2f5e8` / `#b1ca70` | concept evidence |
| graph canvas | `#fbfcf7` with `#bdcabc` 1 px dots every 20 px | graph background |

### Dark theme (sampled)

| Token | Value | Use |
|---|---|---|
| page bg | `#080f1c` | main area |
| sidebar bg | `#0c1524` | left rail |
| panel bg | `#0f1f31` to `#0f2136` | search panel, graph panel |
| card bg | `#111e32` | trajectory cards |
| strip bg | `#0c1828` | four-cell stat strip |
| line | `#243b54` | borders, dividers |
| accent (cyan) | `#77e4f0` | CTA button, active nav bar, headline line 2, seed node |
| accent soft | `#9aeff6` on `#153649` | selected segment, active nav |
| text | `#f1f5f9` approx | headings |
| muted | `#8fa3b8` approx | body, captions |
| concept node | amber ring on `#524126` | concept nodes |
| author node | `#2c476d` | author nodes |

### Signal colours (both themes)

These map 1:1 to the values of `runs.found_via`. Never add a sixth without adding it to the SET first.

| `found_via` | Label | Light bg / text |
|---|---|---|
| `kw` | Keyword | `#e9eddd` / `#486023` |
| `vec` | Meaning | `#e9e5f1` / `#66508b` |
| `cite` | Citation | `#dfebe9` / `#1a6059` |
| `concept` | Concept | `#f5e8d8` / `#915a23` |
| `author` | Author | `#e2eaf3` / `#355d81` |

Graph node colours follow the same family: paper `#d0e1ba` (seed `#115b50`), concept `#f0d9b4`, author `#bdcee2`.

## 2. Typography

| Role | Light prototype | Dark mockup |
|---|---|---|
| UI and body | Arial, Helvetica, sans-serif, 14 px / 1.55 | a grotesk sans (Inter class) |
| Eyebrow labels | monospace 10 px, uppercase, 1.7 px tracking | monospace, uppercase, wide tracking |
| Numbers and tech strip | as body | monospace |
| Accent | Georgia italic (`.serif`) for one word in the hero and the research-question card | none |

| Element | Size | Weight | Tracking |
|---|---|---|---|
| Hero h1 | 55 px (44 at 1100, 43 at 760) | 500 | -2.5 px |
| Page h1 | 38 px | 500 | -1.7 px |
| h2 | 22 px | 500 | -0.6 px |
| h3 | 17 px | 500 | -0.3 px |
| Result title | 19 px | 400 | normal |
| Search input | 18 px | 400 | normal |
| Big number | 23 to 27 px | 400 | -1 px |
| Chip | 10 px | 400 | normal |

## 3. Layout and spacing

| Item | Value |
|---|---|
| Shell | fixed sidebar 214 px + fluid workspace |
| Top bar | 78 px high, bottom border, breadcrumb left, status pill + collection + avatar right |
| Main | max-width 1600 px, padding 34 px 42 px |
| Radius | 16 px cards, 8 to 9 px buttons and nav, 5 to 6 px chips |
| Shadow | `0 14px 40px #193b3808` on the search panel only |
| Results layout | list + 290 px side column |
| Graph layout | canvas + 270 px side column |
| Paper layout | content + 300 px side column |

Breakpoints:

| Width | Change |
|---|---|
| ≥ 1600 | more top padding, taller hero |
| ≤ 1100 | sidebar 180 px, side columns 250 px, graph side column moves below |
| ≤ 760 | sidebar becomes a top bar with horizontal nav, all grids one column, CTA full width |

## 4. Components

| Component | Anatomy | Notes |
|---|---|---|
| Sidebar | logo + wordmark, subtitle, 4 nav items, footer (project, owners, "MariaDB 11.8.9 · LitSearch") | active item: lime bg (light) or cyan bar + tinted bg (dark) |
| Top bar | breadcrumb `Workspace / <page>`, status pill, collection name, avatar "CH" | status pill must say what is real (see rules) |
| Search panel | label, input (max 2000 chars, required), primary button "Find papers ↗", method segmented control, hint text | segmented: Keyword, Meaning, Fused, CiteHop; `aria-pressed` on each |
| Example card | eyebrow `01 / CITATIONS`, question, arrow | click fills the query and runs the search |
| Stat strip (dark) | 4 cells: MariaDB full-text, BGE · 768 dimensions, Bounded graph walks, RRF → weighted rank | static facts, not metrics |
| Numbers row | 3 big numbers with captions | counts come from the DB, see SCREENS.md |
| Result item | rank (mono), title link, meta line, chips, abstract, footer with provenance text + "Why this paper? ↗" | graph-only results get the highlight style and the eyebrow "A connection beyond text" |
| Chip | coloured label per `found_via` value | one chip per value in the SET |
| Pipeline | vertical line with dots, bold step + muted caption | used for "Behind the results" and "Readable path" |
| Score row | label left, value right, bottom border | metadata and provenance tables |
| Graph canvas | SVG, dotted background, legend bottom-left | nodes focusable, Enter/Space selects |
| Node detail card | eyebrow, name, description, chips, score rows, primary button | updates on node select |
| Metric card | eyebrow metric name, value (`—` when no run), caption | never show a number without a run |
| Ablation table | CONFIG, DEFINITION, RECALL@5, RECALL@20, nDCG@10, MRR, STATE | config C row highlighted as reference |
| Empty state | icon, h2, text, one secondary action | used by loading, empty, error, missing |
| Note | tinted box, 11 px | honesty and disclaimer text |
| Toast | fixed bottom right, ink bg, 5.5 s, `role="status"` | transient feedback |
| Skeleton | pulsing bar | loading only; disabled by reduced motion |

## 5. Iconography

Unicode glyphs, not an icon font:

| Glyph | Meaning |
|---|---|
| `⌕` | search nav, empty state |
| `⌘` | graph explorer nav |
| `▥` | experiments nav |
| `⚙` | settings nav |
| `▤` | paper node |
| `◇` | concept node, missing state |
| `A` | author node |
| `↗` | go / open |
| `!` | error |
| `◌` | loading |

## 6. Accessibility (required, not optional)

- Skip link "Skip to content" to `#main`.
- Focus ring: 3 px solid `#a54829`, offset 4 px, on buttons, links, inputs, selects and graph nodes.
- Segmented buttons set `aria-pressed`.
- Graph nodes: `role="button"`, `tabindex="0"`, `aria-label="Inspect <name>"`, Enter and Space select.
- Every graph has a text alternative: the "View accessible connection list" `<details>`.
- State panels use `role="status"`, the error panel uses `role="alert"`.
- On route change: scroll to top and move focus to `#main`.
- `prefers-reduced-motion: reduce` turns off all animation and the card hover lift.
- Colour is never the only signal: chips carry text, nodes carry a glyph.
