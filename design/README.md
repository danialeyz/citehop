# CiteHop frontend handoff

Design version: 1.0. Visual direction approved by the user on 2026-09-29.
Delivery status: frontend specifications complete; matching browser PNG capture pending.

Extract this archive into the repository root. It contains one top-level `design/` folder. Do not replace the repository's root CLAUDE.md, AGENTS.md, SQL, requirements or application files.

## Start

- Open `START_HERE.html` for desktop and mobile views of the actual prototype.
- Open `prototype/index.html` for the canonical interactive design.
- `CITEHOP_PREVIEW.html` is the generated, self-contained equivalent.
- Give the coding agent the text in `AGENT_PROMPT.md`.

## Authority

1. User-approved scientific visual direction and the original project requirements.
2. `source/CITEHOP_BOOTSTRAP.md` for backend constraints and domain facts.
3. `prototype/index.html`, `styles.css` and `app.js` for visual and interaction reference.
4. `docs/` for screen behavior, accessibility, integration and acceptance criteria.
5. Browser captures generated from those exact source files.

The old print-rendered PNGs did not match the HTML. They are retained only in `reference-boards/` as explicitly superseded historical material. They are not implementation targets. `screenshots/` intentionally contains no claimed matching PNGs until browser capture succeeds.

## File map

| Path | Use |
| --- | --- |
| AGENT_PROMPT.md | Copy-ready implementation brief |
| AGENTS.md | Rules for agents editing this design package |
| START_HERE.html | Live desktop/mobile comparison using the same HTML |
| prototype/ | Canonical HTML, CSS and JavaScript |
| CITEHOP_PREVIEW.html | Generated standalone prototype |
| assets/ | Original SVG logo and JSON tokens |
| contracts/ | Proposed view-model schema and fictional example |
| docs/01–04 | Scope, design system, screens, integration |
| docs/05–07 | Build plan, approval, validation record |
| docs/08–11 | Components, state rules, backlog, content standards |
| docs/12-CAPTURE-AND-PARITY.md | Exact browser capture workflow |
| scripts/ | Standalone build and browser capture scripts |
| screenshots/ | Destination for verified browser PNGs and manifest |
| reference-boards/ | Superseded print-rendered PNGs; do not implement from these |
| source/ | Unchanged source document |

## Generate matching PNGs locally

From the repository root:

```sh
cd design
npm install
npx playwright install chromium
npm run capture
```

This is design tooling only. It does not add Node or Playwright to the Python application's runtime. The script starts a loopback-only server, opens the actual prototype in Chromium, captures desktop and mobile screens and records source hashes and browser details. It does not inject screenshot-only CSS or rewrite controls. See the capture document for limitations and reproducibility.

## Scope and truthfulness

The app remains Streamlit/Python/MariaDB unless a separate architecture change is approved. The handoff covers search, results, paper detail, graph exploration, experiments and development settings. All prototype papers, authors, graph links and provenance are fictional. No search, experiment or database integration has run.

A–L meanings, score semantics and several parameter decisions are absent from the attached document. Those are backend blockers, not an invitation to invent requirements. Implement the available UI and honest unknown states while those definitions are resolved.
