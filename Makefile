COMPOSE = docker compose --env-file .env -f docker/docker-compose.yml
PY = .venv/bin/python
API_PORT ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: help venv frontend-install db-up db-down db-restart db-shell check sql api frontend frontend-check e2e test test-graph test-model graph-import graph-status api-types venv-ml embed-smoke embed embed-status rag-validate eval graph-retrieval-eval lint locks
help: ## list targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'
venv: ## install locked Python runtime and dev dependencies (requires uv, Connector/C)
	uv sync --locked
venv-ml: ## venv plus locked torch/transformers for C05 embeddings
	uv sync --locked --extra ml
frontend-install: ## install locked frontend dependencies
	npm ci --prefix frontend
db-up: ## start both databases and wait for health
	$(COMPOSE) up -d --wait
db-down: ## stop databases; preserve volumes
	$(COMPOSE) down
db-restart: ## restart databases and wait for health
	$(COMPOSE) restart
	$(COMPOSE) up -d --wait
db-shell: ## open SQL shell with configured credentials
	$(COMPOSE) exec db sh -c 'exec mariadb -u"$$MARIADB_USER" -p"$$MARIADB_PASSWORD" "$$MARIADB_DATABASE"'
check: ## real database connections and native vector check
	$(PY) -m citehop.check
sql: ## run trusted SQL file: make sql FILE=sql/smoke.sql
	@test -n "$(FILE)" || (echo 'Set FILE=path/to/file.sql'; exit 1)
	$(PY) -m citehop.apply_sql "$(FILE)"
api: ## run FastAPI on localhost (one development worker)
	$(PY) -m uvicorn citehop.api.main:app --reload --host 127.0.0.1 --port $(API_PORT)
api-types: ## regenerate OpenAPI JSON and frontend/lib/api/schema.d.ts after API schema changes
	$(PY) scripts/export_openapi.py
	npm --prefix frontend run api:types
frontend: ## run Next.js on localhost
	npm --prefix frontend run dev -- --port $(FRONTEND_PORT)
frontend-check: ## lint, typecheck, unit tests and production build
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend test
	npm --prefix frontend run build
e2e: ## browser journey search → answer → citation → graph → dashboard (needs a running stack; one generator call)
	BASE=http://127.0.0.1:$(FRONTEND_PORT) npm --prefix frontend run e2e
test: ## backend smoke/unit tests without databases
	$(PY) -m pytest -m 'not db and not neo4j and not model'
test-model: ## real BGE tokenizer/model tests (needs venv-ml; downloads the pinned model once)
	$(PY) -m pytest -m model
test-graph: ## Neo4j tests; set CITEHOP_TEST_NEO4J_URI/_PASSWORD to a DISPOSABLE instance
	$(PY) -m pytest -m neo4j
graph-import: ## rebuild the Neo4j graph from MariaDB (explicit, never automatic)
	$(PY) -m citehop.graph import
graph-status: ## graph ready/stale/rebuilding/unavailable plus versions
	$(PY) -m citehop.graph status
embed-smoke: ## chunk + embed the 10 smoke articles (resumable; skips current work)
	$(PY) -m citehop.embed run --subset smoke
embed: ## chunk + embed every loaded article (resumable; skips current work)
	$(PY) -m citehop.embed run
embed-status: ## chunk coverage and stale rows for the active configuration
	$(PY) -m citehop.embed status
rag-validate: ## live search + generation check (3 generator calls; needs venv-ml and embedded corpus)
	$(PY) scripts/validate_rag.py
eval: ## C08 retrieval + answer evaluation into results/runs/<run_id>/ (needs venv-ml, embedded corpus, Ollama)
	$(PY) -m citehop.evaluate
graph-retrieval-eval: ## S02 experiment: graph-assisted vs core vector retrieval into results/experiments/s02/ (needs venv-ml, embedded corpus, ready graph)
	$(PY) -m citehop.graph_retrieval eval
lint: ## Python lint
	.venv/bin/ruff check citehop tests scripts/check_persistence.py scripts/search_fixture.py scripts/validate_rag.py \
		scripts/export_openapi.py scripts/smoke_api.py
locks: ## explicitly refresh Python lock and pip exports after dependency changes
	uv lock
	uv export --no-dev --no-emit-project -o requirements.txt
	uv export --no-emit-project -o requirements-dev.txt
	uv export --no-dev --extra ml --no-emit-project -o requirements-ml.txt
