# app/: the CiteHop demo UI (cards #28, #28.5)

Before writing any code here, read `design/AGENT_PROMPT.md`, `design/AGENTS.md` and the numbered docs in `design/docs/`.
The approved design is handoff 1.0 in `design/` (dark "scientific observatory" direction).
`docs/design/` is the superseded v0.1 light sketch. Do not implement from it.

The short version:
- Canonical visual source: `design/prototype/` (index.html, styles.css, app.js). Current captures: `design/screenshots/`. Never use `design/reference-boards/` as a target.
- Stay on Streamlit + Python + MariaDB. No SPA or HTTP API without a separate decision.
- Prototype records are fictional. Never load them into the DB or ship them as live data.
- No invented scores, metrics, latency, A to L definitions, weight meanings or evidence quotes. Show pending or unknown states.
- Every result keeps all `found_via` labels. Graph-only needs candidate-set provenance, not just a citation chip.
- Build view models in adapters (`design/docs/04-DATA-AND-INTEGRATION.md`, `design/contracts/`). No SQL in layout code.
- BIGINT ids stay exact (strings in anything JavaScript touches).
- Graph queries are bounded: depth limit in the recursive part, plus the render cap.
- Escape all database text before putting it in HTML.
