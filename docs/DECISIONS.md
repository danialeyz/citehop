# Decisions

One entry per decision. Newest last. Format:

```markdown
## D-<n> <title>
- Date: YYYY-MM-DD
- Decision: one sentence.
- Why: two sentences.
- Alternatives: what we did not pick.
```

## D-1 MariaDB 11.8.9 pinned

- Date: 2026-09-29
- Decision: compose and CI use `mariadb:11.8.9`. `make check` fails on any other version.
- Why: the `lts` tag moved to 12.3. 11.8.9 fixes cosine recall after a restart.
- Alternatives: `lts` or `latest` (the version can change under us).

## Open

Filled by the phase that makes them (see MIGRATION_HANDOFF.md section 6 and CITEHOP_BOOTSTRAP.md 5.5):

- D-2 to D-10 from the bootstrap (LitSearch, corpusid key, bge-base, one vector table per model, index after load, "MariaDB full-text", 20/80 split, quoted concepts, `found_via` as a SET). Recorded in M2 and M3.
- Index M and ef_search (#21, M5)
- a, b, c weights, query prefix, hop count (#25, M7)
- Extraction model (#14.5), concept merge threshold (#15.5), venue name cleaning (#12.7) (M6)
