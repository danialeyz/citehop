COMPOSE = docker compose --env-file .env -f docker/docker-compose.yml
PY = .venv/bin/python
API_PORT ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: help venv frontend-install db-up db-down db-restart db-shell check sql api frontend frontend-check test test-graph graph-import graph-status lint locks
help: ## list targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'
venv: ## install locked Python runtime and dev dependencies (requires uv, Connector/C)
	uv sync --locked
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
frontend: ## run Next.js on localhost
	npm --prefix frontend run dev -- --port $(FRONTEND_PORT)
frontend-check: ## lint, typecheck and production build
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend run build
test: ## backend smoke/unit tests without databases
	$(PY) -m pytest -m 'not db and not neo4j'
test-graph: ## Neo4j tests; set CITEHOP_TEST_NEO4J_URI/_PASSWORD to a DISPOSABLE instance
	$(PY) -m pytest -m neo4j
graph-import: ## rebuild the Neo4j graph from MariaDB (explicit, never automatic)
	$(PY) -m citehop.graph import
graph-status: ## graph ready/stale/rebuilding/unavailable plus versions
	$(PY) -m citehop.graph status
lint: ## Python lint
	.venv/bin/ruff check citehop tests scripts/check_persistence.py
locks: ## explicitly refresh Python lock and pip exports after dependency changes
	uv lock
	uv export --no-dev --no-emit-project -o requirements.txt
	uv export --no-emit-project -o requirements-dev.txt
