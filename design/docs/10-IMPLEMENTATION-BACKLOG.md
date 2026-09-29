# Frontend implementation backlog

This backlog is derived from the handout and approved design. FE identifiers are handoff work items, not existing Notion card IDs. Danial owns the demo in the source; backend integration needs coordination with Akshat's tables/FULLTEXT/CTE work.

| ID | Work | Dependency | Acceptance |
| --- | --- | --- | --- |
| FE-01 | Theme and shell | Approved visual direction | Tokens, navigation, headings, mobile layout |
| FE-02 | Search composer | FE-01 | Four methods, validation, submit, retained query |
| FE-03 | Result components | FE-01 | Rank, full labels, honest nulls, stable IDs |
| FE-04 | Detail and evidence | FE-03 | Exact quotations, metadata, return context |
| FE-05 | Mock state coverage | FE-02–04 | Loading, empty, error, partial, missing metadata |
| FE-06 | Search adapter | Backend #16–24 | Real outputs, no UI retrieval logic, stale response guard |
| FE-07 | Graph view and inspector | #28.5 data contract | Bounded traversal, direction, selection, readable list |
| FE-08 | Evaluation reader | #25–27 definitions/results | Explicit split, A–L, null states, C reference |
| FE-09 | Development settings | Confirmed parameter semantics | Correct mapping, validation, server test lock |
| FE-10 | Responsive/accessibility pass | FE-01–09 | Keyboard, zoom, contrast, long and missing content |
| FE-11 | Screenshot parity | Current prototype revision | Direct browser captures and matching source hashes |
| FE-12 | Final integration review | Required project checks | Measured verification, limitations and docs updated |

## What can proceed now

Theme, shell, query form, components, placeholder states, fixtures and screenshot tooling. The incomplete A–L definitions do not block rendering an honest pending experiment view.

## Blocked decisions

| Missing input | Effect | Safe interim behavior |
| --- | --- | --- |
| A–L definitions | Cannot execute or label experiments accurately | Twelve pending-definition rows |
| a/b/c formula | Cannot name weights by signal or explain contributions | Neutral parameter names and unknown scores |
| Real search output | No live retrieval | Explicit fixture mode |
| Graph path serialization | No real path explanation | Missing evidence state, no invented edges |
| Run identity/history model | Cannot persist repeated run history safely | Read approved results only |
| Real corpus/enrichment counts | Cannot show verified coverage | Expected or unknown labels |

## Definition of implementation done

Every supported screen uses real data or explicitly communicates an unavailable feature. No fixture content can be mistaken for live retrieval. All source backend invariants hold. The repository checks pass without weakening gates. Actual browser captures cover desktop and mobile and are inspected. Remaining defects and blocked items are recorded by identifier, not hidden behind a generic “complete” label.
