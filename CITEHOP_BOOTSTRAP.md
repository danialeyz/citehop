# CiteHop bootstrap handout for Claude Code

This file tells Claude Code how to create the CiteHop repository from an empty folder: tooling, database, schema, Python package skeleton, tests, CI and the project documents. It covers Week 0 on the board plus the scaffolding the later cards build on. It does not load data or run experiments.

---

## 0. How to use this file (for Danial and Akshat)

1. Make an empty folder, for example `~/code/citehop`, and put this file in it.
2. Install first: Docker Desktop, Python 3.11, git, and MariaDB Connector/C.
   - macOS: `brew install mariadb-connector-c`
   - Ubuntu/Debian: `sudo apt-get install -y libmariadb-dev`
   - Windows: use WSL2 with Ubuntu, then the Ubuntu line.
3. Open Claude Code in that folder and paste this prompt:

```text
Read CITEHOP_BOOTSTRAP.md completely before doing anything.
Then execute the phases in section 6 in order, A to G.
After each phase: run its Check, show me the output, commit, and wait for my "go" before the next phase.
Follow section 2 (rules) at all times. If something in the file is wrong or fails, stop and tell me instead of improvising.
```

4. When all phases are done, push to GitHub and share the repo with your teammate.

Links (private until shared):
- Design: https://claude.ai/artifact/Xm3zXFbuHntBrVcBos1ajw
- Graph Explorer: https://claude.ai/artifact/3tWT2zVd9Yma8QagZMGbXQ
- Task board (Notion, Tier One Tasks): https://app.notion.com/p/41ef857fb23f4e259802f67962a207f9

---

## 1. Project in one paragraph (context for Claude Code)

CiteHop is a scientific paper search engine built entirely inside **MariaDB 11.8.9**, for a university Databases course (team of two beginners: Danial and Akshat). It searches the **LitSearch** benchmark (64,183 ML/NLP papers, 597 test questions, MIT licence) in three ways:
- keyword search with a FULLTEXT index
- meaning search with a `VECTOR(768)` column from `BAAI/bge-base-en-v1.5` and an HNSW vector index
- graph search that walks citations, authors and LLM-extracted concepts with recursive CTEs

The results are fused with RRF and reranked with a weighted score. The research question is whether graph links find correct papers that words and meaning miss. It is answered with a 12-configuration ablation (A to L) graded in SQL against the LitSearch answer key.

---

## 2. Rules for Claude Code (hard)

1. **Pin MariaDB to `mariadb:11.8.9`.** Never `lts` (now 12.3) or `latest`.
2. **Every vector index uses `DISTANCE=cosine`.** The default is euclidean, and a cosine query on it silently scans the whole table.
3. **Vector search queries have exactly this shape:** `ORDER BY VEC_DISTANCE_COSINE(col, ?) LIMIT k`. No math inside ORDER BY, no missing LIMIT. Compute `1 - d` outside.
4. **Vector indexes are added after bulk loading,** never in `schema.sql`. Add no other index to a table after its vector index exists.
5. **Vectors are bound as bytes:** `np.asarray(v, dtype="<f4").tobytes()`, with a length check first. A wrong-length vector returns random rows without an error.
6. **Do not guess LitSearch field names.** Loader code that needs them stays a stub that raises `NotImplementedError("see data/NOTES.md, card #9")` until card #9 records them.
7. **No secrets in git.** `.env` is ignored, and `.env.example` holds placeholders only.
8. **Never tune on the test split.** Code that reads test questions must take the split as an explicit argument.
9. **Recursive CTEs always have a depth limit** in the recursive part.
10. **Idempotent scripts.** Every `make` target can run twice without errors or duplicates (`IF NOT EXISTS`, `INSERT IGNORE`).
11. **Small commits,** one per phase, message format `phase X: <what>` (later: `#<card>: <what>`).
12. **Writing style for docs:** short sentences, plain words, no em dashes, no filler. Tables and code over prose.
13. **Stop and ask** before deleting anything, changing a pinned version, or when a Check fails twice.

---

## 3. Target repository layout

```text
citehop/
├── CLAUDE.md                      # standing instructions for future Claude Code sessions
├── README.md
├── Makefile
├── pyproject.toml
├── requirements.txt               # core runtime
├── requirements-ml.txt            # sentence-transformers (heavy, not in CI)
├── requirements-dev.txt           # pytest, ruff
├── .env.example
├── .gitignore
├── .editorconfig
├── docker/
│   ├── docker-compose.yml
│   └── my.cnf
├── sql/
│   ├── schema.sql                 # 6 core tables            (card #8)
│   ├── kg_schema.sql              # 5 KG tables + kg_links   (card #12.5)
│   └── README.md                  # one line per query file, filled as cards land
├── citehop/
│   ├── __init__.py
│   ├── db.py                      # connect() from .env
│   ├── apply_sql.py               # run a .sql file statement by statement
│   ├── check.py                   # prints OK + version
│   ├── embed.py                   # embed_query / embed_doc + length guard (card #14)
│   ├── load_corpus.py             # stub (card #10)
│   ├── load_questions.py          # stub (card #12)
│   ├── load_vectors.py            # stub (card #15)
│   ├── enrich.py                  # stub (card #12.7)
│   ├── extract.py                 # stub (card #14.5)
│   ├── load_concepts.py           # stub (card #15.5)
│   ├── search.py                  # stub (cards #16 to #24)
│   └── evaluate.py                # stub (card #19)
├── scripts/
│   └── inspect_litsearch.py       # card #9
├── notebooks/
│   └── .gitkeep                   # embed_colab.ipynb comes with card #13
├── app/
│   └── .gitkeep                   # streamlit_app.py comes with card #28
├── tests/
│   ├── test_embed_guard.py        # unit, no DB, no model
│   └── test_schema.py             # integration, needs DB (marker: db)
├── data/                          # gitignored except NOTES.md
│   └── NOTES.md
├── results/
│   └── .gitkeep
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── DECISIONS.md
│   ├── EXPERIMENTS.md
│   ├── RESULTS.md
│   ├── TRAPS.md
│   ├── GLOSSARY.md
│   └── CONTRIBUTING.md
└── .github/
    ├── workflows/ci.yml
    └── pull_request_template.md
```

---

## 4. Files with exact content

Create these exactly. Where a section says "write", Claude Code writes the content from the outline given.

### 4.1 `.gitignore`

```gitignore
.env
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
*.egg-info/
data/*
!data/NOTES.md
results/*.png
.DS_Store
.ipynb_checkpoints/
```

### 4.2 `.editorconfig`

```ini
root = true
[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
indent_style = space
indent_size = 4
[Makefile]
indent_style = tab
[*.{yml,yaml,json,md,sql}]
indent_size = 2
```

### 4.3 `.env.example`

```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=citehop
DB_PASS=citehop
DB_NAME=citehop
S2_API_KEY=
ANTHROPIC_API_KEY=
```

### 4.4 `docker/my.cnf`

```ini
[mariadb]
mhnsw_max_cache_size = 1G
innodb_ft_min_token_size = 2
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

### 4.5 `docker/docker-compose.yml`

```yaml
services:
  db:
    image: mariadb:11.8.9
    environment:
      MARIADB_ROOT_PASSWORD: root
      MARIADB_DATABASE: citehop
      MARIADB_USER: citehop
      MARIADB_PASSWORD: citehop
    ports:
      - "3306:3306"
    volumes:
      - ./my.cnf:/etc/mysql/conf.d/citehop.cnf:ro
      - dbdata:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 30
volumes:
  dbdata:
```

### 4.6 `requirements.txt`, `requirements-ml.txt`, `requirements-dev.txt`

```text
# requirements.txt
mariadb>=1.1.12
numpy>=1.26
pandas>=2.1
python-dotenv>=1.0
tqdm>=4.66
requests>=2.31
datasets>=2.19
pyarrow>=15
```

```text
# requirements-ml.txt
-r requirements.txt
sentence-transformers>=3.0
streamlit>=1.36
matplotlib>=3.8
```

```text
# requirements-dev.txt
-r requirements.txt
pytest>=8.0
ruff>=0.5
```

Once everything works in Phase D, run `pip freeze` into `requirements.lock.txt` and commit it.

### 4.7 `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "citehop"
version = "0.1.0"
description = "Scientific paper search in MariaDB: FULLTEXT + vectors + a knowledge graph"
requires-python = ">=3.11"

[tool.setuptools]
packages = ["citehop"]

[tool.pytest.ini_options]
markers = ["db: needs a running MariaDB (make db-up)"]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

### 4.8 `Makefile` (recipes must be indented with a TAB)

```makefile
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
	@read -p "Delete the database volume? [y/N] " a && [ "$$a" = "y" ] && $(COMPOSE) down -v && $(COMPOSE) up -d --wait

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
```

Placeholder targets are added later by their cards: `load`, `questions`, `embed-load`, `enrich`, `extract`, `concepts`, `eval`, `app`. Do not add them now.

### 4.9 `sql/schema.sql` (card #8)

```sql
CREATE TABLE IF NOT EXISTS papers (
  corpusid   BIGINT PRIMARY KEY,
  title      TEXT NOT NULL,
  abstract   TEXT,
  year       SMALLINT NULL,
  n_cited_by INT NOT NULL DEFAULT 0,
  FULLTEXT KEY ft_title_abstract (title, abstract)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS citations (
  citing_id BIGINT NOT NULL,
  cited_id  BIGINT NOT NULL,
  PRIMARY KEY (citing_id, cited_id),
  KEY k_cited (cited_id, citing_id),
  CONSTRAINT fk_cit_citing FOREIGN KEY (citing_id) REFERENCES papers(corpusid),
  CONSTRAINT fk_cit_cited  FOREIGN KEY (cited_id)  REFERENCES papers(corpusid)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS emb_bge_base (
  corpusid BIGINT PRIMARY KEY,
  emb      VECTOR(768) NOT NULL,
  CONSTRAINT fk_emb_paper FOREIGN KEY (corpusid) REFERENCES papers(corpusid)
) ENGINE=InnoDB;
-- vector index is added AFTER loading (card #15), never here

CREATE TABLE IF NOT EXISTS queries (
  query_id INT PRIMARY KEY,
  text     TEXT NOT NULL,
  kind     ENUM('specific','broad') NOT NULL,
  origin   ENUM('inline','author') NOT NULL,
  split    ENUM('dev','test') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qrels (
  query_id INT NOT NULL,
  corpusid BIGINT NOT NULL,
  PRIMARY KEY (query_id, corpusid),
  CONSTRAINT fk_qrels_q FOREIGN KEY (query_id) REFERENCES queries(query_id),
  CONSTRAINT fk_qrels_p FOREIGN KEY (corpusid) REFERENCES papers(corpusid)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS runs (
  config    VARCHAR(8) NOT NULL,
  query_id  INT NOT NULL,
  rnk       SMALLINT NOT NULL,
  corpusid  BIGINT NOT NULL,
  score     DOUBLE NOT NULL,
  found_via SET('kw','vec','cite','concept','author') NOT NULL,
  PRIMARY KEY (config, query_id, rnk),
  CONSTRAINT fk_runs_q FOREIGN KEY (query_id) REFERENCES queries(query_id),
  CONSTRAINT fk_runs_p FOREIGN KEY (corpusid) REFERENCES papers(corpusid)
) ENGINE=InnoDB;
```

### 4.10 `sql/kg_schema.sql` (card #12.5)

```sql
CREATE TABLE IF NOT EXISTS authors (
  author_id BIGINT PRIMARY KEY,
  name      VARCHAR(300) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS paper_authors (
  corpusid  BIGINT NOT NULL,
  author_id BIGINT NOT NULL,
  position  TINYINT NOT NULL,
  PRIMARY KEY (corpusid, author_id),
  KEY k_author (author_id, corpusid),
  CONSTRAINT fk_pa_paper  FOREIGN KEY (corpusid)  REFERENCES papers(corpusid),
  CONSTRAINT fk_pa_author FOREIGN KEY (author_id) REFERENCES authors(author_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS venues (
  venue_id INT AUTO_INCREMENT PRIMARY KEY,
  name     VARCHAR(200) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE papers ADD COLUMN IF NOT EXISTS venue_id INT NULL;

ALTER TABLE papers ADD CONSTRAINT fk_paper_venue
  FOREIGN KEY IF NOT EXISTS (venue_id) REFERENCES venues(venue_id);

CREATE TABLE IF NOT EXISTS concepts (
  concept_id INT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(200) NOT NULL,
  kind       ENUM('method','task','dataset','metric') NOT NULL,
  df         INT NOT NULL DEFAULT 0,
  emb        VECTOR(768) NOT NULL,
  UNIQUE KEY uq_kind_name (kind, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- vector index on concepts.emb is added after loading (card #15.5)

CREATE TABLE IF NOT EXISTS concept_aliases (
  alias      VARCHAR(200) PRIMARY KEY,
  concept_id INT NOT NULL,
  CONSTRAINT fk_alias_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS paper_concepts (
  corpusid   BIGINT NOT NULL,
  concept_id INT NOT NULL,
  relation   ENUM('proposes','uses','evaluates_on','addresses') NOT NULL,
  evidence   TEXT NOT NULL,
  confidence FLOAT NOT NULL DEFAULT 1,
  PRIMARY KEY (corpusid, concept_id, relation),
  KEY k_concept (concept_id, corpusid),
  CONSTRAINT fk_pc_paper   FOREIGN KEY (corpusid)   REFERENCES papers(corpusid),
  CONSTRAINT fk_pc_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE OR REPLACE VIEW kg_links (a, b, rel) AS
SELECT CONCAT('paper:', citing_id), CONCAT('paper:', cited_id), 'cites' FROM citations
UNION ALL SELECT CONCAT('paper:', cited_id), CONCAT('paper:', citing_id), 'cited_by' FROM citations
UNION ALL SELECT CONCAT('author:', author_id), CONCAT('paper:', corpusid), 'wrote' FROM paper_authors
UNION ALL SELECT CONCAT('paper:', corpusid), CONCAT('author:', author_id), 'written_by' FROM paper_authors
UNION ALL SELECT CONCAT('paper:', corpusid), CONCAT('concept:', concept_id), relation FROM paper_concepts
UNION ALL SELECT CONCAT('concept:', concept_id), CONCAT('paper:', corpusid), relation FROM paper_concepts
UNION ALL SELECT CONCAT('paper:', corpusid), CONCAT('venue:', venue_id), 'published_in'
          FROM papers WHERE venue_id IS NOT NULL
UNION ALL SELECT CONCAT('venue:', venue_id), CONCAT('paper:', corpusid), 'published_in'
          FROM papers WHERE venue_id IS NOT NULL;
```

If MariaDB rejects the `FOREIGN KEY IF NOT EXISTS` line, stop and report it. Do not drop the foreign key.

### 4.11 `citehop/__init__.py`

```python
"""CiteHop: scientific paper search in MariaDB."""
__version__ = "0.1.0"
```

### 4.12 `citehop/db.py`

```python
"""Database connection from .env."""
import os

import mariadb
from dotenv import load_dotenv

load_dotenv()


def connect(database: str | None = None) -> mariadb.Connection:
    """Open a connection. autocommit is off: call conn.commit() yourself."""
    return mariadb.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "citehop"),
        password=os.getenv("DB_PASS", "citehop"),
        database=database or os.getenv("DB_NAME", "citehop"),
        autocommit=False,
    )
```

### 4.13 `citehop/apply_sql.py`

```python
"""Run a .sql file statement by statement: python -m citehop.apply_sql sql/schema.sql"""
import re
import sys
from pathlib import Path

from citehop.db import connect


def statements(sql: str) -> list[str]:
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def main(path: str) -> None:
    conn = connect()
    cur = conn.cursor()
    stmts = statements(Path(path).read_text(encoding="utf-8"))
    for i, s in enumerate(stmts, 1):
        cur.execute(s)
        print(f"[{i}/{len(stmts)}] ok: {s.splitlines()[0][:70]}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m citehop.apply_sql <file.sql>")
    main(sys.argv[1])
```

Our SQL files contain no semicolons inside strings, so splitting on `;` is safe. Keep it that way.

### 4.14 `citehop/check.py`

```python
"""make check: prints OK and the server version, fails on the wrong version."""
import sys

from citehop.db import connect

EXPECTED = "11.8.9"

conn = connect()
cur = conn.cursor()
cur.execute("SELECT VERSION()")
(version,) = cur.fetchone()
cur.execute(
    "SHOW VARIABLES WHERE Variable_name IN ('mhnsw_max_cache_size', 'innodb_ft_min_token_size')"
)
settings = dict(cur.fetchall())
conn.close()

print(f"server: {version}")
for k, v in settings.items():
    print(f"{k} = {v}")
if not version.startswith(EXPECTED):
    sys.exit(f"FAIL: expected MariaDB {EXPECTED}, got {version}")
print(f"OK: connected to MariaDB {version}")
```

### 4.15 `citehop/embed.py` (card #14)

```python
"""The only place text becomes vectors. Questions and papers must never be embedded differently."""
import numpy as np

MODEL = "BAAI/bge-base-en-v1.5"
DIM = 768
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_model = None


def _m():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # heavy, import lazily

        _model = SentenceTransformer(MODEL)
    return _model


def to_bytes(v) -> bytes:
    """float32 little-endian bytes for MariaDB VECTOR. Raises on the wrong length."""
    arr = np.asarray(v, dtype="<f4")
    if arr.shape != (DIM,):
        raise ValueError(f"expected {DIM} values, got shape {arr.shape}")
    return arr.tobytes()


def embed_query(text: str, prefix: bool = True) -> bytes:
    q = (QUERY_PREFIX + text) if prefix else text
    return to_bytes(_m().encode(q, normalize_embeddings=True))


def embed_doc(title: str, abstract: str | None) -> bytes:
    return to_bytes(_m().encode(f"{title}. {abstract or ''}".strip(), normalize_embeddings=True))
```

### 4.16 Stub modules

For each of `load_corpus.py`, `load_questions.py`, `load_vectors.py`, `enrich.py`, `extract.py`, `load_concepts.py`, `search.py` and `evaluate.py`, write:
- a module docstring naming its Notion card number and one sentence of purpose
- the public function names from the design with type hints (see the list below)
- bodies that raise `NotImplementedError("card #N")`
- a `if __name__ == "__main__":` block that prints `not implemented yet: card #N`

The public functions:
- `load_corpus.main()`
- `load_questions.main(seed: int = 42)`
- `load_vectors.main()`
- `enrich.main()`
- `extract.main(limit: int | None = None)`
- `load_concepts.main()`
- `search.keyword(q, k=100)`, `search.vector(q, k=100)`, `search.fused(q)`, `search.citehop(q, a=0.7, b=0.2, c=0.1, signal="expand", hops=1, weighted=True, damp=True, prior=False)`
- `evaluate.main(config: str, split: str, db: str | None = None)`

### 4.17 `scripts/inspect_litsearch.py` (card #9)

```python
"""Card #9: download LitSearch, print its real fields, save parquet.

Record the results by hand in data/NOTES.md.
"""
from pathlib import Path

from datasets import load_dataset

out = Path("data/raw")
out.mkdir(parents=True, exist_ok=True)

for name in ["query", "corpus_clean"]:
    try:
        ds = load_dataset("princeton-nlp/LitSearch", name, split="full")
    except ValueError:
        print(load_dataset("princeton-nlp/LitSearch", name))  # shows the real split names
        raise
    print(f"\n=== {name}: {ds.num_rows} rows ===")
    print(ds.features)
    row = ds[0]
    print({k: (v[:200] if isinstance(v, str) else v) for k, v in row.items()})
    ds.to_parquet(out / f"litsearch_{name}.parquet")
print("\nSaved to data/raw/. Now fill data/NOTES.md by hand (card #9).")
```

### 4.18 `data/NOTES.md`

```markdown
# LitSearch field notes (card #9)

Filled by hand after `make inspect`. Later loaders read field names from here.

| Set | Rows (expected) | Rows (actual) |
|---|---|---|
| query | 597 | |
| corpus_clean | 64,183 | |

## corpus_clean fields
| Meaning | Field name | Python type |
|---|---|---|
| paper id | | |
| title | | |
| abstract | | |
| cited ids list | | |
| year (if any) | | |

## query fields
| Meaning | Field name | Values |
|---|---|---|
| question text | | |
| specific or broad | | |
| inline or author-written | | |
| correct paper ids | | |

## Example rows
(paste 3 of each)
```

### 4.19 `tests/test_embed_guard.py`

```python
import numpy as np
import pytest

from citehop.embed import DIM, to_bytes


def test_right_length_gives_3072_bytes():
    assert len(to_bytes(np.zeros(DIM))) == DIM * 4


@pytest.mark.parametrize("n", [0, 384, 767, 769, 1024])
def test_wrong_length_raises(n):
    with pytest.raises(ValueError):
        to_bytes(np.zeros(n))


def test_little_endian_float32():
    b = to_bytes(np.arange(DIM))
    assert np.frombuffer(b, dtype="<f4")[5] == 5.0
```

### 4.20 `tests/test_schema.py`

```python
import pytest

from citehop.db import connect

CORE = {"papers", "citations", "emb_bge_base", "queries", "qrels", "runs"}
KG = {"authors", "paper_authors", "venues", "concepts", "concept_aliases", "paper_concepts"}


@pytest.mark.db
def test_all_tables_exist():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SHOW FULL TABLES")
    rows = {name: kind for name, kind in cur.fetchall()}
    conn.close()
    assert CORE <= rows.keys()
    assert KG <= rows.keys()
    assert rows.get("kg_links") == "VIEW"


@pytest.mark.db
def test_vector_column_is_768():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'emb_bge_base' AND COLUMN_NAME = 'emb'"
    )
    (col_type,) = cur.fetchone()
    conn.close()
    assert col_type.lower() == "vector(768)"


@pytest.mark.db
def test_no_vector_index_before_loading():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SHOW CREATE TABLE emb_bge_base")
    ddl = cur.fetchone()[1].upper()
    conn.close()
    assert "VECTOR KEY" not in ddl and "VECTOR INDEX" not in ddl
```

### 4.21 `.github/workflows/ci.yml`

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      db:
        image: mariadb:11.8.9
        env:
          MARIADB_ROOT_PASSWORD: root
          MARIADB_DATABASE: citehop
          MARIADB_USER: citehop
          MARIADB_PASSWORD: citehop
        ports: ["3306:3306"]
        options: >-
          --health-cmd="healthcheck.sh --connect --innodb_initialized"
          --health-interval=5s --health-timeout=5s --health-retries=30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: sudo apt-get update && sudo apt-get install -y libmariadb-dev
      - run: pip install -r requirements-dev.txt && pip install -e .
      - run: ruff check citehop tests scripts
      - run: pytest -m "not db"
      - run: python -m citehop.apply_sql sql/schema.sql && python -m citehop.apply_sql sql/kg_schema.sql
      - run: python -m citehop.apply_sql sql/schema.sql && python -m citehop.apply_sql sql/kg_schema.sql  # idempotency
      - run: pytest -m db
```

CI can't load `my.cnf`, so the FULLTEXT token size is the default there. That's fine for schema tests. Say so in `docs/CONTRIBUTING.md`.

### 4.22 `.github/pull_request_template.md`

~~~markdown
**Card:** #<number> <title> (Notion link)

**What changed**
-

**Check from the card** (paste the output)
```text
```

- [ ] `make lint` and `make test` pass
- [ ] Numbers added to docs/RESULTS.md with the command that produced them
- [ ] Decisions added to docs/DECISIONS.md if any were made
~~~

---

## 5. Documents to write (content outlines)

Write each in the style from rule 12. Use Mermaid diagrams where noted (GitHub renders them).

### 5.1 `CLAUDE.md` (for every future Claude Code session)
Must contain, in this order:
1. **What CiteHop is:** 3 lines, taken from section 1.
2. **Commands:** the Makefile targets with one line each.
3. **Hard rules:** copy section 2, rules 1 to 13.
4. **How to work a card:**
   - The Notion card body is the spec, and its "Check" is the acceptance test.
   - Branch `w<week>/<card>-<slug>`, for example `w2/13-embed-colab`.
   - Commit messages `#<card>: <what>`.
   - Update docs/RESULTS.md and docs/DECISIONS.md in the same PR.
5. **Where things live:** a condensed version of the section 3 tree.
6. **The two owners:** Danial owns meaning, extraction and the demo. Akshat owns tables, FULLTEXT and recursive CTEs. Shared work is marked Both on the board.
7. **Pointers:** docs/ARCHITECTURE.md, docs/DATA_MODEL.md and docs/TRAPS.md, to read before any SQL work.

### 5.2 `README.md`
Sections:
- CiteHop (2-line pitch)
- Status (a table of Week 0 to 4 with checkboxes)
- Requirements
- Quick start (`cp .env.example .env`, `make venv`, `make db-up`, `make check`, `make schema kg-schema`)
- Project layout
- How search works (5 bullets)
- Docs index
- Credits and licences:
  - LitSearch (MIT)
  - bge-base-en-v1.5 (MIT)
  - Semantic Scholar data (attribution required)
  - SciFact (CC BY-NC, not redistributed)

### 5.3 `docs/ARCHITECTURE.md`
- Build-once vs every-search, with two Mermaid flowcharts:
  - Build: LitSearch goes to load_corpus, embed (Colab), load_questions, enrich and extract, all into MariaDB tables.
  - Search: question goes to keyword and vector, then RRF, graph expansion (citations, concepts, authors), rerank, top 20, runs.
- The 12 configs, with a pointer to EXPERIMENTS.md.
- Why one database: joins between vectors, text and graph in one query, and no sync between stores.

### 5.4 `docs/DATA_MODEL.md`
- A Mermaid `erDiagram` of all 12 tables.
- A per-table section: purpose, keys, indexes and why each index exists.
- The `kg_links` view and when to use it (exploring and the Graph Explorer) vs typed tables (search).
- Load order: papers, citations, emb, queries, qrels, KG tables, runs.

### 5.5 `docs/DECISIONS.md`
Format: `## D-<n> <title>`, then Date, Decision, Why (2 sentences), Alternatives. Pre-fill these, all dated 2026-09-29:
1. D-1 MariaDB 11.8.9 pinned (the lts tag moved to 12.3; 11.8.9 fixes cosine recall after restart)
2. D-2 LitSearch as the benchmark (597 questions, citation ids included, MIT)
3. D-3 Semantic Scholar corpusid as the primary key everywhere
4. D-4 bge-base-en-v1.5, 768 dims, cosine (best of the small models on the scientific BEIR sets, simple to call)
5. D-5 One vector table per embedding model (one vector index per table)
6. D-6 Vector indexes added after bulk load
7. D-7 Keyword baseline is called "MariaDB full-text", not BM25
8. D-8 Dev/test split 20/80, stratified by kind and origin, seed 42
9. D-9 LLM concept extraction must quote the abstract; unquoted links are dropped
10. D-10 found_via is a SET so one result can be found several ways

Then leave empty stubs for the decisions the cards will make:
- index M and ef_search (#21)
- a, b, c weights (#25)
- query prefix (#25)
- hop count (#25)
- extraction model (#14.5)
- concept merge threshold (#15.5)
- venue name cleaning (#12.7)

### 5.6 `docs/EXPERIMENTS.md`
- The A to L table: config, what it adds, the question it answers.
- Metrics defined in one line each: Recall@5 (specific questions), Recall@20 (broad questions), nDCG@10, MRR, found-only-via-graph, p50/p95 latency.
- Split rules: tune on dev only, report on test only.
- Significance: paired bootstrap, 1,000 resamples, 95% interval vs config C.
- Published baselines to cite (LitSearch paper, Recall@5 on specific questions):
  - BM25 50.0
  - E5-large-v2 56.2
  - GritLM-7B 74.8
  - Google Scholar 20.5 (80 inline-citation questions only)
- Expectation from the literature: graph expansion helps weak retrievers and hurts when unweighted. For example, LitSearch one-hop expansion moved GritLM from 73.2 to 70.3.

### 5.7 `docs/RESULTS.md`
Empty tables, each with a "command / SQL that produced it" column:
- Load counts (#10)
- Graph stats (#11)
- Embedding time on CPU and the title self-check (#13)
- Index build time (#15)
- Search time with and without the index (#17)
- SciFact nDCG@10, target near 74.04 (#20)
- Index sweep (#21)
- Enrichment coverage (#12.7)
- Extraction precision and recall (#14.5)
- Concept stats (#15.5)
- Main table A to L (#26)
- Latency (#27)

### 5.8 `docs/TRAPS.md`
One row per trap, with Symptom, Cause, Fix:
- euclidean default
- query shape
- 16 MB cache
- wrong vector length
- index after vector index
- Docker lts tag
- FULLTEXT min token size and "not BM25"
- recursive CTE without a depth limit, and the anchor CAST
- LLM invents concepts
- generic concepts become hubs
- Semantic Scholar keys refused for free email domains
- OpenAlex needs a key since Feb 2026

### 5.9 `docs/GLOSSARY.md`
Terms, one line each:
- embedding
- cosine distance
- HNSW
- M
- ef_search
- FULLTEXT
- RRF
- seed
- hop
- recursive CTE
- citation graph
- knowledge graph
- concept
- df/IDF
- shared references (bibliographic coupling)
- cited together (co-citation)
- qrels
- dev/test split
- Recall@k
- nDCG@10
- MRR

### 5.10 `docs/CONTRIBUTING.md`
- Branch and commit rules (from CLAUDE.md)
- PR template use
- Weekly 10-minute check-in
- How to run tests locally vs CI
- The CI my.cnf note
- "Never commit data/ or .env"

---

## 6. Build phases (execute in order, stop after each)

### Phase A: repository and tooling
1. `git init -b main`.
2. Create the layout from section 3. Add `.gitkeep` files in empty folders.
3. Write the files from 4.1, 4.2, 4.3, 4.6, 4.7 and 4.8.
4. `cp .env.example .env`
5. `make venv`, then activate `.venv`.

**Check:** `make help` lists the targets, and `python -c "import mariadb, citehop; print('ok')"` prints ok.
**Commit:** `phase A: repo skeleton and tooling`

### Phase B: database (card #2)
1. Write `docker/my.cnf` and `docker/docker-compose.yml` (4.4, 4.5).
2. Write `citehop/__init__.py`, `db.py` and `check.py` (4.11, 4.12, 4.14).
3. `make db-up && make check`

**Check:** the output ends with `OK: connected to MariaDB 11.8.9...` and shows `mhnsw_max_cache_size = 1073741824` and `innodb_ft_min_token_size = 2`.
**Commit:** `phase B: MariaDB 11.8.9 in Docker with project config`

### Phase C: schema (cards #8 and #12.5)
1. Write `citehop/apply_sql.py`, `sql/schema.sql` and `sql/kg_schema.sql` (4.13, 4.9, 4.10).
2. `make schema kg-schema`, then run it a second time.
3. Write `tests/test_schema.py` (4.20) and run `make test-db`.
4. Write `sql/README.md` with one line per SQL file.

**Check:**
- Both runs of `make schema kg-schema` succeed.
- `make test-db` passes 3 tests.
- `make db-shell` then `SHOW FULL TABLES;` lists 12 tables and 1 view.

**Commit:** `phase C: core and knowledge graph schema`

### Phase D: package skeleton (cards #14 and #9 scaffolding)
1. Write `citehop/embed.py` (4.15) and the stubs (4.16).
2. Write `scripts/inspect_litsearch.py` (4.17) and `data/NOTES.md` (4.18).
3. Write `tests/test_embed_guard.py` (4.19).
4. `make lint && make test`
5. `pip freeze > requirements.lock.txt`

**Check:** ruff is clean, and `make test` passes 7 tests (1 + 5 parametrized + 1).
**Commit:** `phase D: package skeleton, embed guard, inspect script`

### Phase E: documents
1. Write `CLAUDE.md`, `README.md` and all of `docs/` from section 5.
2. Check that each doc follows rule 12 (no em dashes: `grep -rn "—" CLAUDE.md README.md docs/` returns nothing).
3. Check that the Mermaid blocks render: paste one into https://mermaid.live if unsure.

**Check:** `ls docs` shows 8 files, and the grep returns nothing.
**Commit:** `phase E: project documents`

### Phase F: CI and PR template
1. Write `.github/workflows/ci.yml` and `.github/pull_request_template.md` (4.21, 4.22).
2. Create a GitHub repo, for example `danialeyz/citehop` (private), and push.

**Check:** the first Actions run is green. If the MariaDB service or `libmariadb-dev` step fails, report the log and stop.
**Commit:** `phase F: CI with MariaDB 11.8.9 service`

### Phase G: card #9 (only if the network allows)
1. `pip install -r requirements-ml.txt` is not needed here, since `datasets` is already in core.
2. `make inspect`
3. Fill `data/NOTES.md` from the printed output. Copy field names exactly.

**Check:** NOTES.md has both row counts and every field name filled in. If Hugging Face is unreachable, stop and say so. Card #9 then stays open on the board.
**Commit:** `#9: LitSearch field notes`

---

## 7. Definition of done for this handout

- [ ] `make db-up && make check` works on both laptops
- [ ] `make schema kg-schema` is idempotent; 12 tables + `kg_links` view exist
- [ ] `make lint`, `make test`, `make test-db` all pass
- [ ] CI is green on GitHub
- [ ] CLAUDE.md, README.md and 8 docs exist and follow the style rule
- [ ] docs/DECISIONS.md has D-1 to D-10
- [ ] data/NOTES.md is filled (or card #9 is still open with the reason noted)
- [ ] Notion cards #2, #5, #6 and #8 (and #9 if Phase G ran) are moved to Review

## 8. Out of scope for this handout

- Loading data (#10, #12)
- Embeddings (#13, #15)
- Search (#16 to #24)
- Experiments (#25 to #27)
- The app and the explorer on real data (#28, #28.5)

Each of these starts from its Notion card, with CLAUDE.md in place.