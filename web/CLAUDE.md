@AGENTS.md

# web/: the CiteHop frontend (cards #28, #28.5)

Stack: React 19 + TypeScript (strict) + Next.js 16 (App Router, Turbopack) + Tailwind CSS v4. Node 22+. Decided 2026-09-29, replacing Streamlit.
Next 16 has breaking changes: read the bundled guide in `node_modules/next/dist/docs/` before using an API (see AGENTS.md).

Before writing any code here, read `design/docs/13-FRONTEND-ARCHITECTURE.md`, then `design/AGENT_PROMPT.md`, `design/AGENTS.md` and the other numbered docs in `design/docs/`.
The approved design is handoff 1.0 in `design/`.

The short version:
- Canonical visual source: `design/prototype/`. Current captures: `design/screenshots/`. Never target `design/reference-boards/`.
- Next.js never connects to MariaDB. It calls the Python API (`citehop/api.py`) from server code via `CITEHOP_API_URL`. No secrets behind `NEXT_PUBLIC_`.
- Types come from `design/contracts/search-view.schema.json` via `npm run gen:types` into `src/lib/types.ts`. Never edit that file. BIGINT ids are strings; never `Number()` them.
- Colours, fonts, radii and breakpoints come from the Tailwind `@theme` in `src/app/globals.css`, mapped from `design/assets/tokens.json`. No raw hex in components.
- Build mobile-first: base styles are the 390 px layout, `wide:` is 760 px and up, `full:` is 1100 px and up.
- No `dangerouslySetInnerHTML`. ESLint enforces it with `react/no-danger`.
- Prototype records are fictional. No invented scores, metrics, latency, A to L definitions, weight meanings or evidence quotes. Show pending or unknown states.
- Every result keeps all `found_via` labels. Graph-only needs candidate-set provenance, not just a citation chip.
- Graph depth is enforced by the API. The UI select is not a safety limit.
- Checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
