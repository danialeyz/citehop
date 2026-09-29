# Agent instructions: building the CiteHop UI

> [!WARNING]
> **Superseded.** This is the v0.1 light sketch. The approved design is handoff 1.0 in [`/design`](../../design/README.md). Do not implement from this folder.

For Claude Code and any other coding agent that touches the demo app (`app/`, card #28) or the graph explorer (card #28.5).
Read this file in full before writing UI code. The project-wide rules in `CLAUDE.md` still apply. This file adds to them and never overrides them.

> [!NOTE]
> `CLAUDE.md` and `docs/DECISIONS.md` are written in bootstrap Phase E. Until then, "rule N" in this file means rule N in section 2 of the bootstrap handout (`CITEHOP_BOOTSTRAP.md`).

## 1. Read order

1. `CLAUDE.md` (project rules 1 to 13).
2. This file.
3. [SCREENS.md](SCREENS.md) for the screen you are building.
4. [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) for tokens and components.
5. Open `citehop-preview-v0.1.html` in a browser and click through the route you are building.
6. `sql/schema.sql` and `sql/kg_schema.sql` for the real column names.

## 2. Source of truth

When two sources disagree, the higher one wins:

| Rank | Source | Decides |
|---|---|---|
| 1 | The Notion card for the task | scope and the Check |
| 2 | `CLAUDE.md` and `docs/DECISIONS.md` | rules and settled choices |
| 3 | `sql/*.sql` and `citehop/*.py` | names, types, what data exists |
| 4 | [SCREENS.md](SCREENS.md) | what each screen shows and where data comes from |
| 5 | `citehop-preview-v0.1.html` | copy, behaviour, states, accessibility |
| 6 | `desktop-search-dark.png` | visual direction for the dark theme |
| 7 | [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | tokens and component specs |

If a lower source asks for data a higher one does not have, stop and ask. Do not add a column to make a mockup work.

## 3. Hard rules for UI work

1. **No fixtures in the product.** The prototype's titles, authors, abstracts, graph and scores are fictional. Never copy them into app code, seed data or tests that run against the real DB.
2. **No invented numbers.** A metric, count, score or latency with no run behind it shows `—` or "Not computed". Hard-coding 64,183 or 597 is allowed only with the word "expected", before data is loaded.
3. **Provenance is the product.** Every result shows one chip per `found_via` value. Graph-only results (no `kw`, no `vec`) always get the highlight and the "A connection beyond text" eyebrow.
4. **Evidence is quoted, never paraphrased.** Concept evidence shows `paper_concepts.evidence` exactly.
5. **Search goes through `citehop.search`.** The UI never builds its own vector or FULLTEXT SQL. If the UI needs something the function does not return, change the function in its own card.
6. **Graph queries are bounded.** Depth limit in the recursive part (rule 9) plus a node cap. The UI depth select is not a safety limit on its own.
7. **Split is explicit.** Anything that reads questions or runs takes `split` as an argument. The Test view has no tuning controls (rule 8).
8. **Read-only by default.** The app does not write to the DB except to `runs`, and only from the evaluation path, never from the search box.
9. **Accessibility is part of done.** Everything in DESIGN_SYSTEM.md section 6 ships. Keyboard-only use must reach every control and every graph node.
10. **Every state exists.** loading, empty, error and missing are built with the screen, not later.
11. **Errors are calm.** Show the state message. Log the exception. Never print a stack trace, SQL or a password in the UI.
12. **Copy follows rule 12.** Short sentences, plain words, no em dashes. Reuse the prototype's copy where it fits.
13. **Do not ship review scaffolding.** No "Review states" bar, no "Design review draft" note, no "Illustrative prototype" pill in the real app.

## 4. How to work a UI card

1. Branch `w<week>/<card>-<slug>`, for example `w4/28-demo-app`.
2. List the screens and states the card covers. Map each element to its source using SCREENS.md.
3. Check every `db` element against the schema. Write the SQL in `citehop/` (not in the app file) with a depth limit where recursive.
4. Build the screen. Tokens first, then layout, then data, then states.
5. Verify, in this order:
   - `make lint` and `make test` pass.
   - Run the app against the local DB and click every state. Force empty with a nonsense query. Force error with `make db-down`.
   - Take a screenshot at 1440 px and at 390 px. Put them next to the matching file in `docs/design/screens/`. Fix visible drift in layout, spacing and hierarchy.
   - Tab through the page with the keyboard only.
6. Commit `#<card>: <what>`. In the PR, paste the screenshots and the Check output.
7. Record any design choice you made in `docs/DECISIONS.md`. If it closes an open decision below, update this file too.

## 5. Open decisions

Do not decide these silently. Ask the owner (Danial owns the demo) or follow a recorded decision.

| ID | Question | Options | Recommendation |
|---|---|---|---|
| UI-1 | Which theme ships? | light (HTML v0.1), dark (PNG), both with a toggle | dark as default, light as print/report view. The PNG is the newer direction; the HTML holds the behaviour spec. |
| UI-2 | App stack | Streamlit (handout: `app/streamlit_app.py`), or a small web server with custom HTML | Streamlit with `st.navigation` pages and injected CSS tokens. Accept lower fidelity on the graph canvas. Revisit only if card #28 allows. |
| UI-3 | Logo | three lime nodes (HTML), three cyan dots (PNG), hop mark (`assets/logo-*.svg`, used by README) | pick one and use it everywhere |
| UI-4 | Return shape of `search.*` | list of dicts, DataFrame, dataclass | a list of dataclasses with `rnk, corpusid, score, found_via` |
| UI-5 | Show venue nodes in the graph? | yes / no | no for #28.5; `kg_links` has them if needed |
| UI-6 | Node cap in the graph explorer | 30, 50, 100 | 50 |
| UI-7 | Full text URL on Paper detail | from Semantic Scholar enrichment (#12.7), or drop the row | drop until #12.7 stores a URL |
| UI-8 | Names for weights a, b, c | from #25 | keep "Parameter a/b/c" until DECISIONS.md names them |

## 6. Streamlit mapping (if UI-2 lands on Streamlit)

| Design element | Streamlit approach |
|---|---|
| Sidebar nav | `st.navigation` with 4 `st.Page` entries, icons from section 5 of DESIGN_SYSTEM.md |
| Tokens | one `st.markdown("<style>…</style>", unsafe_allow_html=True)` block built from DESIGN_SYSTEM.md, in a single helper |
| Search panel | `st.form` with `st.text_input` (max_chars=2000) and `st.segmented_control` for the method |
| Result item and chips | `st.markdown` with small HTML; escape every DB string with `html.escape` |
| Side cards | `st.columns([3, 1])` + `st.container(border=True)` |
| Graph canvas | a custom SVG rendered in `st.html`, or `streamlit-agraph` if added to `requirements-ml.txt` in its own card |
| Accessible list | `st.expander("View accessible connection list")` |
| States | `st.spinner` for loading; an `st.container` with the state copy for empty, error, missing |
| Settings | `st.number_input`, `st.selectbox`, `st.toggle`, stored in `st.session_state` |
| Export plan | `st.download_button` with a CSV |

Escape all database text before putting it in HTML. Titles and abstracts can contain `<` and `&`.

## 7. Done checklist for a UI card

- [ ] Every element on the screen is mapped to a source in SCREENS.md, and no fixture text remains.
- [ ] loading, empty, error and missing all render and were clicked through.
- [ ] Chips match `found_via` exactly. Graph-only results are highlighted.
- [ ] No number is shown without a run or a live count behind it.
- [ ] Graph queries have a depth limit and a node cap.
- [ ] Keyboard-only walkthrough works. Focus ring visible. Reduced motion respected.
- [ ] Screenshots at 1440 px and 390 px are in the PR, next to the design renders.
- [ ] `make lint` and `make test` pass.
- [ ] Decisions recorded in `docs/DECISIONS.md`; closed rows updated in section 5 above.
