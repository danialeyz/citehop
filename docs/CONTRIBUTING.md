# Contributing

## Branches and commits

- Migration: one phase per branch and one commit per phase, `migrate M<n>: <what>`. Open the PR into `migrate/citehop`.
- After the migration: branch `w<week>/<card>-<slug>`, commit `#<card>: <what>`.
- Put new numbers in [RESULTS.md](RESULTS.md) and new decisions in [DECISIONS.md](DECISIONS.md) in the same PR.

## Tests

| Command | Needs | Runs in CI |
|---|---|---|
| `make lint` | venv | yes |
| `make test` | venv, no services | yes |
| `make test-db` | `make db-up`, `CITEHOP_TEST_DB_NAME` set to a disposable database | yes |
| `make check` | `make db-up` (MariaDB and Neo4j) | no |
| `make frontend-check` | `make frontend-install` | yes (lint, typecheck, tests, build) |
| `make test-model`, `make test-graph` | ML extra, disposable Neo4j | no |

`make test-db` drops and recreates tables in `CITEHOP_TEST_DB_NAME`. Never point it at `DB_NAME`. The tests refuse to run if the two match.

## CI and my.cnf

CI runs MariaDB 11.8.9 as a service container, which cannot mount `docker/my.cnf`. CI therefore uses the default `innodb_ft_min_token_size` (3) and `mhnsw_max_cache_size`. That is fine for schema and db tests. Do not compare search numbers from CI with local ones.

## Never commit

- `.env` or any key. `.env.example` holds placeholders only.
- `data/` (only `data/NOTES.md` is tracked).
