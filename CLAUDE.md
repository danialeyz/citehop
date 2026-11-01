# CiteHop

## What CiteHop is

A scientific paper search engine that runs inside MariaDB 11.8.9. It searches LitSearch (64,183 ML/NLP papers, 597 questions) with FULLTEXT, `VECTOR(768)` from `BAAI/bge-base-en-v1.5`, and graph walks over citations, authors and concepts in recursive CTEs.

The repo is mid-migration from the Wikipedia RAG prototype (100 articles, Neo4j graph, Next.js UI) to that target. The plan is `MIGRATION_HANDOFF.md` and the target files are in `CITEHOP_BOOTSTRAP.md`. Both must be in the repo root of your checkout. Progress and gaps: [docs/MIGRATION_AUDIT.md](docs/MIGRATION_AUDIT.md). Prompts per phase: [docs/MIGRATION_PROMPTS.md](docs/MIGRATION_PROMPTS.md).

## Commands

`make help` lists every target. The ones you need most:

| Target | What it does |
|---|---|
| `make venv` | `uv sync --locked` (Python runtime and dev deps) |
| `make db-up` / `db-down` | start or stop MariaDB and Neo4j (volumes kept) |
| `make db-reset` | delete the volumes and start fresh (asks first) |
| `make check` | connections, version 11.8.9, `my.cnf` settings, a cosine check |
| `make schema` / `kg-schema` | apply `sql/schema.sql` / `sql/kg_schema.sql` |
| `make sql FILE=...` | apply any trusted SQL file |
| `make lint` | ruff |
| `make test` | unit tests, no services |
| `make test-db` | db tests in `CITEHOP_TEST_DB_NAME` (a disposable database) |
| `make inspect` | download LitSearch and print its fields (from M3) |
| `make api` / `make frontend` | run FastAPI on :8000 / Next.js on :3000 |
| `make frontend-check` | frontend lint, typecheck, tests, build |
| `make locks` | refresh `uv.lock` and `requirements*.txt` (only after a dependency change) |

## Hard rules

Migration:
1. Keep it running. After every phase the prototype's main flow still works, or the audit says what replaces it.
2. No silent deletions. List every removed file, feature or table in the phase report, with the reason and the replacement.
3. Adapt, don't rewrite, code that already meets a target requirement.
4. Old and new side by side when switching engines. Build, prove with tests and numbers, switch callers, then delete the old path in its own commit.
5. One commit per phase, `migrate M<n>: <what>`, PR into `migrate/citehop`.

Target:
6. Pin `mariadb:11.8.9`. Never `lts` or `latest`.
7. Every vector index uses `DISTANCE=cosine`.
8. Vector search has exactly this shape: `ORDER BY VEC_DISTANCE_COSINE(col, ?) LIMIT k`. Compute `1 - d` outside.
9. Vector indexes are added after bulk loading, never in a schema file. No other index is added to a table after its vector index exists.
10. Vectors are bound as bytes, `np.asarray(v, dtype="<f4").tobytes()`, after a length check.
11. Never guess LitSearch field names. Read them from `data/NOTES.md` (card #9).
12. Never tune on the test split. Code that reads test questions takes the split as an argument.
13. Every recursive CTE has a depth limit.
14. No secrets in git, and no SQL built with f-strings.
15. Every `make` target can run twice without errors or duplicates.
16. Docs: short sentences, plain words, no em dashes. Tables and code over prose.
17. Stop and ask before: dropping data, changing a pinned version, changing the corpus or the embedding model, any step that costs money, or when a check fails twice.

## How to work

- During the migration: one phase per session, from MIGRATION_HANDOFF.md section 6. Post the section 7 report and stop.
- After the migration: the Notion card body is the spec and its Check is the acceptance test. Branch `w<week>/<card>-<slug>`, commit `#<card>: <what>`.
- Update [docs/RESULTS.md](docs/RESULTS.md) and [docs/DECISIONS.md](docs/DECISIONS.md) in the same PR.
- Run `make lint && make test && make test-db` before every commit.

## Where things live

```text
citehop/           Python package: db.py, apply_sql.py, check.py, search, embed, evaluate
citehop/api/       FastAPI under /api/v1
citehop/graph/     Neo4j import (removed in M8)
sql/               SQL files: schema.sql, kg_schema.sql; corpus_schema.sql (legacy, until M8)
frontend/          Next.js 16 UI (see frontend/AGENTS.md)
docker/            docker-compose.yml and my.cnf
tests/             pytest; markers db, neo4j, model
eval/, results/    prototype questions and saved runs (history)
docs/              architecture, data model, decisions, traps, results
.github/           CI: Python + MariaDB service job, frontend job
```

## Owners

Danial owns meaning, extraction and the demo. Akshat owns tables, FULLTEXT and recursive CTEs. Shared work is marked Both on the board.

## Read before SQL work

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_MODEL.md](docs/DATA_MODEL.md) and [docs/TRAPS.md](docs/TRAPS.md). DATA_MODEL describes the target tables (M2). ARCHITECTURE still describes the prototype until M4 rewrites it.
