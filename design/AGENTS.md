# Agent rules for /design

The scientific observatory visual direction is approved. Preserve graphite/navy surfaces, cyan evidence paths, violet semantic labels, technical typography and the evidence-first hierarchy.

The original bootstrap remains authoritative for backend behavior. This package is a frontend handoff, not permission to execute bootstrap phases or change the architecture.

## Editing rules

- Edit `prototype/index.html`, `prototype/styles.css`, `prototype/app.js` as the canonical UI source.
- Run `node scripts/build-preview.mjs` after source edits. Never hand-edit CITEHOP_PREVIEW.html.
- Update matching docs and assets/tokens.json in the same change.
- Use only actual browser captures for screenshots/. Do not use print rendering, rebuilt SVG mockups or image generation to represent the implemented HTML.
- No capture-only CSS, hidden controls, substitute fonts, replacement inputs or changed table columns.
- reference-boards/ is superseded history. Do not copy its layout differences back into the app.
- Keep fixtures explicitly fictional. No fabricated scores, latency, benchmark gains, extracted quotes or corpus load counts.
- Approval covers visual design, not unknown A–L definitions or score semantics.
- Do not store secrets, real datasets, node_modules or browser binaries in this folder.
- Follow repository-level checks and instructions when implementing web/ (Next.js, see docs/13-FRONTEND-ARCHITECTURE.md).

## Completion

Read docs/10-IMPLEMENTATION-BACKLOG.md and docs/12-CAPTURE-AND-PARITY.md. Record performed checks separately from pending checks. Do not claim screenshots match until capture runs against the current source hashes and the results are inspected.
