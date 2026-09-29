Read `design/README.md`, `design/AGENTS.md` and numbered documents in `design/docs/`. Read the repository's root instructions and `design/source/CITEHOP_BOOTSTRAP.md` before touching backend code.

Implement CiteHop's frontend using the approved scientific observatory direction. The visual direction is approved; do not ask again merely to start implementation. Use `design/prototype/index.html`, styles.css and app.js as the canonical design reference. `design/reference-boards/` contains superseded print images that did not match the HTML. Never use them as pixel targets.

First run the browser capture workflow in `design/docs/12-CAPTURE-AND-PARITY.md` in your normal development environment. Inspect the generated PNGs and record actual results. No screenshot-only styles or replacement controls are permitted. If browser rendering is blocked, report that precisely and continue with implementation work that can be verified; do not claim pixel parity.

Preserve the planned Streamlit app and Python/MariaDB architecture. Do not introduce a separate SPA or API without a separate architecture decision. Implement the six screens and required states in dependency order using docs/10-IMPLEMENTATION-BACKLOG.md. Keep retrieval, graph traversal and evaluation in backend modules; convert their real outputs into the view models described in docs/04-DATA-AND-INTEGRATION.md and contracts/.

Keep the visual hierarchy, typography, colors, layouts and responsive behavior. Prefer native accessible Streamlit controls. When a graph custom component is necessary, isolate it, pass only sanitized display data and provide the native readable connection list. Avoid fragile global CSS targeting generated Streamlit class names.

All prototype records are fictional. Do not load them into the research database. Do not invent A–L definitions, metric values, latency, score meanings, parameter mappings or concept evidence. Implement explicit pending/unknown states for missing backend features. Continue unblocked UI work while tracking these dependencies.

Preserve every bootstrap invariant: MariaDB 11.8.9; cosine vector indexing and canonical query shape; checked 768-dimensional little-endian byte vectors; correct index creation order; explicit dev/test split; bounded recursive queries; no secrets; no guessed LitSearch raw fields.

Results must retain every found_via label. Graph-only requires candidate-set provenance. Concept evidence must quote the stored abstract exactly. Preserve null metadata and BIGINT identifiers. Test data must not be used for tuning, and this restriction must hold at the backend boundary.

Work in reviewable increments. Run required repository checks and the focused acceptance checks in design/docs/. Do not weaken tests or change pinned versions to make the UI pass. At completion report: implemented screens, backend integration status, validation actually run, remaining blocked items and paths to current browser captures.
