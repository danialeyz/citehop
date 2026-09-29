# app/: the CiteHop demo UI (cards #28, #28.5)

Before writing any code here, read `docs/design/AGENT_INSTRUCTIONS.md` in full.
It links the screen specs, the design system and the clickable prototype.

The short version:
- The design in `docs/design/` uses fictional fixtures. Never copy its titles, authors, graph or numbers into the app.
- No number without a run behind it. Show `—` or "Not computed".
- Search goes through `citehop.search`. No vector or FULLTEXT SQL in this folder.
- Every result shows one chip per `found_via` value. Graph-only results are highlighted.
- Graph queries have a depth limit and a node cap.
- Build loading, empty, error and missing states with every screen.
- Escape all database text before putting it in HTML.
- Open decisions (theme, stack, logo, and more) are in section 5 of the instructions. Ask, do not guess.
