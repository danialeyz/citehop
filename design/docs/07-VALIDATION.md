# Validation record

Package version: 1.0. Date: 2026-09-29.

Completed during design preparation:
- JavaScript syntax checks.
- 17 DOM-level checks covering 12 routes, method selection, search submission, graph node inspection, settings preview and the 12-row ablation table.
- Original source copy matched the attached document byte for byte.
- Self-contained preview generated directly from canonical HTML/CSS/JS.
- Proposed JSON contract example validated against its schema.

Known defect and disposition:
- Previous PNGs used a print renderer that substituted controls and altered layout. The user reported the mismatch.
- Those images moved to reference-boards/. They are historical only.
- screenshots/ is reserved for direct browser captures; none are asserted as complete in this delivery.

Current environment blockers:
- Local Chromium could not run in the execution environment.
- The available browser rejected the workspace-file URL under its URL security policy.
- No alternative browser access was attempted after that policy rejection.

Pending local acceptance:
- Execute npm run capture with Chromium in the development environment.
- Inspect the PNGs and capture manifest from the same source revision.
- Verify real keyboard interactions, focus visibility, 200% zoom and accessibility.
- Test actual Next.js, Python API and MariaDB integration when backend cards are complete.

The capture script was syntax-checked but could not be run end-to-end here. No claim of browser parity, WCAG conformance or production readiness is made.

## Browser capture run (FE-11), 2026-09-29

Performed on macOS (Darwin 25.2), Node 24.9.0, Playwright 1.62.1, Chrome Headless Shell 151.0.7922.34.

- Package integrity: all 48 MANIFEST.json hashes matched the extracted files before any change.
- `node scripts/build-preview.mjs` reproduced CITEHOP_PREVIEW.html byte for byte.
- `npm run capture`: status passed, 16 PNGs, no page errors, no page-level horizontal overflow at 1440 or 390 px.
- Capture source hashes equal the MANIFEST.json hashes for prototype/index.html, styles.css and app.js.
- All 16 PNGs were opened and inspected by the agent against the live prototype.

Observations from inspection:

| Capture | Observation | Disposition |
| --- | --- | --- |
| desktop-* (full page) | The fixed sidebar's background ends at 1050 px on pages taller than the viewport. | Artifact of full-page capture of a `position: fixed` element. Not visible when scrolling in a browser. Not a layout defect. |
| mobile-* | The horizontal nav strip clips "Search settings" at the right edge. | Intended: the strip scrolls (`overflow: auto`). |
| mobile-experiments | "Ablation study / A–L" wraps between "A–" and "L". | Minor. Use a non-breaking hyphen or `white-space: nowrap` on the suffix in production. |
| mobile-experiments | The ablation table scrolls inside its container. | Intended, per docs/05. |

Still pending:
- Owner review of the captures (step 6 of docs/12).
- Real keyboard, focus, 200% zoom and contrast checks.
- Next.js, Python API and MariaDB integration once backend cards land.
