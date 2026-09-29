COMPOSE = docker compose -f docker/docker-compose.yml
PY = python

.PHONY: help venv db-up db-down db-reset db-shell check schema kg-schema test test-db lint inspect

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'

venv:            ## create .venv and install core + dev deps
	python3.11 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements-dev.txt && pip install -e .

db-up:           ## start MariaDB 11.8.9 and wait until healthy
	$(COMPOSE) up -d --wait

db-down:         ## stop MariaDB (data kept)
	$(COMPOSE) down

db-reset:        ## DELETE all data and start fresh (asks first)
	@read -p "Delete the database volume? [y/N] " a; \
	if [ "$$a" = "y" ]; then $(COMPOSE) down -v && $(COMPOSE) up -d --wait; else echo "Cancelled."; fi

db-shell:        ## open a mariadb prompt
	$(COMPOSE) exec db mariadb -ucitehop -pcitehop citehop

check:           ## verify connection and version
	$(PY) -m citehop.check

schema:          ## create the 6 core tables (safe to rerun)
	$(PY) -m citehop.apply_sql sql/schema.sql

kg-schema:       ## create the knowledge graph tables and view (safe to rerun)
	$(PY) -m citehop.apply_sql sql/kg_schema.sql

test:            ## unit tests, no DB
	pytest -m "not db"

test-db:         ## integration tests, needs make db-up
	pytest -m db

lint:            ## ruff
	ruff check citehop tests scripts

inspect:         ## card #9: download LitSearch and print its fields
	$(PY) scripts/inspect_litsearch.py
