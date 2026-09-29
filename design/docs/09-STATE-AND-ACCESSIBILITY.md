# State and accessibility contract

## Search lifecycle

| From | Event | Next | Data rule |
| --- | --- | --- | --- |
| Idle | Valid submit | Loading | Snapshot query, method, parameters and request ID |
| Loading | New submit | Loading | New request ID invalidates older response |
| Loading | Success with rows | Ready | Replace results atomically |
| Loading | Success with no rows | Empty | Keep query and settings |
| Loading | Partial retrieval | Partial | Name missing branches; preserve provenance |
| Loading | Failure | Error | Keep last successful result separate and marked stale |
| Loading | Cancel | Idle or prior Ready | Ignore late response; cancel server work only if supported |
| Ready | Open paper | Detail | Preserve result context and scroll position |
| Detail | Back | Ready | Restore selected result focus |

The prototype demonstrates state appearances. It does not implement asynchronous retrieval. Production must implement cancellation and stale-response handling in the adapter/application layer.

## Experiment lifecycle

Definitions pending → configured → queued → running → measured or failed. Test split uses a frozen configuration. Unknown metrics are null, not zero. A partial run is visibly partial and cannot silently enter the primary aggregate table. Persist run metadata only through a separately approved backend storage design.

## Accessibility acceptance

- Meaningful page title and one primary heading per screen.
- Navigation landmark, main landmark, visible skip link and consistent keyboard order.
- Visible labels and error descriptions linked to inputs.
- Focus indicator on all controls, with at least 3:1 contrast against neighboring colors.
- Normal text at least 4.5:1 contrast; large text at least 3:1.
- Primary touch targets at least 44px; avoid tiny graph nodes as the only action path.
- No color-only provenance, selected state, validation or edge meaning.
- Results completion announced once, politely, with count and partial status.
- Loading uses aria-busy; failures announce actionable errors without stack traces.
- Graph selection usable through keyboard and a semantic list/table.
- Zoom to 200% without losing functionality; horizontal scrolling confined to large tables.
- Respect reduced motion. No essential information in animation.
- Evidence quotations are selectable text. No screenshot-only text.

These are implementation acceptance targets. They have not been established by an automated accessibility audit in this environment.

## Data safety in the UI

Escape titles, abstracts, author names, query text and evidence quotes. Do not render untrusted values as raw HTML. Avoid query strings containing credentials or internal database connection information. Do not cache test answers or secrets in localStorage. Treat in-browser fixtures as public illustrative content.
