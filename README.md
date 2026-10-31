<p align="center"><img alt="CiteHop" src="assets/logo-dark.svg" width="480"></p>

CiteHop is a local university Databases course project by Danial and Akshat: answer questions from **100 English ML Wikipedia articles**, cite retrieved passages, and explore real article links/categories. Use a 10-article smoke subset and 30 checked questions. MariaDB owns native vector retrieval and relational filtering; Neo4j Community holds a manually imported graph projection. Article links are not scholarly citations.

C01 provides the local foundation only. Search, Library, Graph, Dashboard, ingestion, generation and evaluation are pending. No feature endpoints, corpus schema, models or fabricated results are included. The earlier scientific-paper/LitSearch, Streamlit, and broad ablation plan is retired. Historical design mockups are references only; follow [current tasks](docs/COURSE_TASKS.md), [architecture](docs/ARCHITECTURE.md) and [UI specification](docs/design/COURSE_UI.md).

## Requirements and pinned stack

- Node **26.12.1**, npm **11.20.0**; Python **3.11** (tested **3.11.18**); uv **0.13.6**.
- Next.js **16.4.3**, React **19.3.1**, TypeScript **5.9.3**, Tailwind **4.3.3**.
- FastAPI **0.162.0**, Uvicorn **0.54.0**, MariaDB Python connector **1.1.14**, Neo4j driver **6.4.1**.
- Docker with Compose; MariaDB **11.8.9**, Neo4j Community **5.26.32**; native Connector/C (tested **3.4.11**).
- `frontend/package-lock.json` and `uv.lock` lock transitive dependencies. `requirements*.txt` are hashed pip exports; `pyproject.toml` is the Python dependency source. ML dependencies are deferred to C05.

Versions were checked against official [Next installation](https://nextjs.org/docs/app/getting-started/installation) (Node >=20.9), [Tailwind Next integration](https://tailwindcss.com/docs/installation/framework-guides/nextjs), [FastAPI releases](https://fastapi.tiangolo.com/release-notes/), [MariaDB 11.8.9 release notes](https://mariadb.com/docs/release-notes/community-server/11.8/11.8.9), [Neo4j releases](https://neo4j.com/release-notes/) and [driver compatibility](https://neo4j.com/docs/python-manual/current/install/) (6.x supports Python >=3.10 and Neo4j 5.x). Exact package versions were confirmed through npm/PyPI. See [Node release policy](https://nodejs.org/en/about/previous-releases).

## Local setup

```sh
# macOS prerequisites (install Node separately using .node-version)
brew install python@3.11 mariadb-connector-c uv
export PATH="/opt/homebrew/opt/mariadb-connector-c/bin:$PATH"
# Debian/Ubuntu: install Python 3.11, build-essential, libmariadb-dev, and uv.
cp .env.example .env
cp frontend/.env.example frontend/.env.local
# Change local placeholder passwords before starting databases.
make venv frontend-install
make db-up
make check
make sql FILE=sql/smoke.sql
make api                    # terminal 1: http://127.0.0.1:8000/docs
make frontend               # terminal 2: http://127.0.0.1:3000
```

`GET /api/v1/health` works directly on port 8000 and through Next on port 3000. HTTP 200 / `status: ok` reports API liveness; `services.mariadb` and `services.neo4j` independently report `ready`/`unavailable`, without exception details or credentials. It performs read-only database probes. No feature routes exist yet. Blocking probes run in FastAPI's thread pool.

Next's `/api/*` rewrite forwards to FastAPI. `API_UPSTREAM` in `frontend/.env.local` is server-only and may also be used by future server-rendered API calls. Never put database/model secrets in frontend files or `NEXT_PUBLIC_*`. Only root `.env` contains database credentials; all environment files except examples are ignored. No model credentials are required for C01.

For port conflicts edit `DB_PORT`, `NEO4J_BOLT_PORT`, `NEO4J_HTTP_PORT` in root `.env`; update `NEO4J_URI` to match Bolt. Use `make api API_PORT=8001` and update frontend `API_UPSTREAM`; use `make frontend FRONTEND_PORT=3001`. Restart Next after changing upstream. Make's API port is a command-line override, not loaded from `.env`.

Compose binds ports to localhost. Use a distinct `COMPOSE_PROJECT_NAME` per checkout to isolate volumes. Named MariaDB data and Neo4j data/log volumes survive `make db-restart` and `make db-down` / `make db-up`. Never run `down -v` against data you need. Existing volumes are not migrated or reset; changing password variables does not change credentials already stored in a volume. Neo4j's initial username is `neo4j`. Docker runs databases only; API/frontend run on the host.

## Development and verification

```sh
make help
make test lint frontend-check
make check                         # live connections + cosine vector query
make sql FILE=sql/smoke.sql         # temporary VECTOR(3) table, no corpus data
make db-shell
.venv/bin/python scripts/check_persistence.py  # unique test row/node, restart, verify, cleanup
make db-restart                     # preserves named volumes
make db-down                       # stops only this Compose project
uv build                           # wheel/sdist include citehop.api
```

`make sql FILE=...` executes trusted local SQL with quoted semicolon handling. It is not a migration framework: DDL implicitly commits, and client `DELIMITER` scripts require the MariaDB CLI. C03 owns the corpus schema. `make locks` refreshes Python locks/exports after intentional dependency edits; commit lockfiles with those edits. Use `npm ci`, not an unpinned scaffold generator, for frontend installs.

Ownership: `frontend/` renders React UI; `citehop/api/` contains thin HTTP routes/schemas; `citehop/` contains database helpers and future business logic; `docker/` contains local infrastructure; `sql/` contains trusted scripts. `app/` is retired. Existing assets and the Python package are reused.

MariaDB's [area 4 assignment](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively) remains central. Neo4j supplements it and must be disclosed in the submission; required MariaDB retrieval/filtering demonstrations remain self-contained. No cloud, auth, queue, synchronization service, separate vector store or broad experiment grid. Wikipedia attribution/revisions and model licensing will be recorded with acquisition/model tasks.
