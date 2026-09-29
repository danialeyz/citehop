# Implementation and acceptance

## Build order for the approved design

1. Confirm bootstrap completion and read repository CLAUDE.md. Do not replay phases A–G against an existing repo.
2. Implement visual tokens (Tailwind @theme) and the app shell in the Next.js app in web/ (docs/13).
3. Implement query entry and the four method choices with a mock adapter. Make fixture mode explicit.
4. Implement results and paper detail using real schema-shaped view models. Support null fields.
5. Integrate keyword/vector/fused/citehop only when those cards are complete. Remove fictional fixtures from production paths.
6. Implement bounded graph retrieval, node selection and an accessible list. Keep graph logic separate from layout.
7. Implement read-only experiment views. Add tuning only after A–L and parameter definitions are approved. Lock test behavior server-side.
8. Verify responsive layouts and required states. Record actual outcomes in the project PR.

## Proposed repository additions

| Path | Responsibility |
| --- | --- |
| web/src/app/layout.tsx | App shell, navigation, skip link |
| web/src/app/globals.css | Tailwind @theme tokens from assets/tokens.json |
| web/src/app/page.tsx, search/ | Composer and result rendering |
| web/src/app/papers/[corpusid]/ | Metadata and evidence |
| web/src/app/graph/ | Graph viewport and readable edge list |
| web/src/app/experiments/ | Read-only metrics and comparison table |
| web/src/app/settings/ | Development parameter controls |
| web/src/lib/api.ts, types.ts | Typed server-side API client; types generated from contracts/ |
| citehop/api.py | Python API: adapters to view models, validation, error mapping |

This organization is a proposal for later cards. Avoid creating empty abstractions just to match the tree. Use the smallest maintainable structure for the course project.

## Superseded: Streamlit guidance

The stack is now Next.js (docs/13). This section is kept for history only.

Use native form submission and session state for query, selected method, paper ID and settings. Keep results in session state until a new successful query replaces them. Do not rerun expensive retrieval because a user expands an evidence panel.

Map colors and type to supported Streamlit theme settings. Use native containers and columns for most layout. Do not rely on unstable generated DOM class names for broad CSS injection. The HTML reference demonstrates desired appearance; pixel-identical custom navigation may require a small custom component. Record that tradeoff before introducing one.

The graph can be a contained custom component if native rendering cannot satisfy node inspection. Pass only sanitized schema-shaped data and selected-node events. Keep a native text/list alternative. Never put database access or secrets in component JavaScript.

That decision was made on 2026-09-29: the frontend is Next.js with a Python API. See docs/13 for the API boundary.

## Interaction acceptance

- Search submits by Enter and click, trims input, preserves query on errors and blocks blank submissions.
- Method selection clearly changes selected state and maps to the correct Python function.
- Results remain in backend rank order, show all found_via values and preserve long titles.
- Paper detail uses stable corpusid and returns to the correct search and scroll position.
- Null abstract, year, venue and author lists have honest fallbacks.
- Graph selection works with mouse and keyboard, and every relation has a readable text equivalent.
- Hop limits are enforced on the server, even if the client sends a larger value.
- Missing evidence never produces a fabricated extraction quote.
- No run, real zero, failed run and partial run render differently.
- Test evaluation cannot mutate or tune settings. Query split is explicit at the backend boundary.
- Parameter a/b/c labels stay neutral until the formula is defined.
- Client-rendered BIGINT IDs retain precision.

## Visual acceptance

Review at 1440px, 1024px, 768px and 390px widths, plus 200% zoom. Desktop side rails align to the result or abstract region. Mobile has a single content column and an internally scrolling experiment table. No page-level horizontal overflow. No title truncation that hides the paper identity. No navigation overlap with content.

Verify text contrast, focus visibility, keyboard order, reduced motion and 44px primary touch targets. Matching browser captures are pending. Superseded print boards are not validation evidence. Follow docs/12-CAPTURE-AND-PARITY.md before accepting PNG references.

## Focused tests

Test the risky boundaries, not CSS implementation details: request-to-function mapping; stale-response handling; null metadata; multiple provenance labels; BIGINT serialization; graph-only classification; finite recursion limit; test split lock; missing metrics; evidence quotation integrity. Use a fixture with overlapping keyword/vector/graph memberships to ensure graph-only is not inferred from a single chip.

Run the repository's required checks. Add an integration test only when the backend feature exists. Do not invent an endpoint or weaken a bootstrap check to make UI tests pass.

## Prototype fidelity

Implemented: hash navigation, responsive templates, sample question selection, search submission, selected retrieval method, paper navigation, graph node inspection, development/test explanatory state, settings preview/reset and CSV plan export.

Demonstrated only: retrieval, ranking, expansion depth, scores, metrics, cancellation, retry, graph-only classification and evidence extraction. The prototype neither queries nor modifies MariaDB. Its review footer is an inspection aid and must not ship in the production app.
