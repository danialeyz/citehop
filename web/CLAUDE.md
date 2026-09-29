# web/: the CiteHop frontend (cards #28, #28.5)

Stack: React + TypeScript (strict) + Next.js (App Router) + Tailwind CSS v4. Decided 2026-09-29, replacing Streamlit.

Before writing any code here, read `design/docs/13-FRONTEND-ARCHITECTURE.md`, then `design/AGENT_PROMPT.md`, `design/AGENTS.md` and the other numbered docs in `design/docs/`.
The approved design is handoff 1.0 in `design/`.

The short version:
- Canonical visual source: `design/prototype/`. Current captures: `design/screenshots/`. Never target `design/reference-boards/`.
- Next.js never connects to MariaDB. It calls the Python API (`citehop/api.py`) from server code via `CITEHOP_API_URL`. No secrets behind `NEXT_PUBLIC_`.
- Types come from `design/contracts/search-view.schema.json`. BIGINT ids are strings; never `Number()` them.
- Colours, fonts, radii and breakpoints come from the Tailwind `@theme` in `src/app/globals.css`, mapped from `design/assets/tokens.json`. No raw hex in components.
- No `dangerouslySetInnerHTML` for titles, abstracts, authors, queries or evidence.
- Prototype records are fictional. No invented scores, metrics, latency, A to L definitions, weight meanings or evidence quotes. Show pending or unknown states.
- Every result keeps all `found_via` labels. Graph-only needs candidate-set provenance, not just a citation chip.
- Graph depth is enforced by the API. The UI select is not a safety limit.
- Checks: `npm run lint`, `npx tsc --noEmit`, `npx vitest run`, `npm run build`.
