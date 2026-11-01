A project for area 4, "Vector search and RAG, natively" for the [MariaDB student database projects, 2026-09](https://mariadb.org/bachelor_hackathon_2026-09/).

<h1 align="center">citehop.</h1>
<p align="center"><strong>Big questions. Clear connections.</strong><br>Search the evidence. Generate a cited answer. Follow the thread.</p>

<p align="center">
  <img src="https://img.shields.io/badge/MariaDB-native_vectors-c6f27b?style=flat-square" alt="MariaDB native vectors">
  <img src="https://img.shields.io/badge/Neo4j-knowledge_graph-c6f27b?style=flat-square" alt="Neo4j knowledge graph">
  <img src="https://img.shields.io/badge/Next.js-research_workspace-1a1d18?style=flat-square" alt="Next.js research workspace">
</p>

<p align="center">
  <a href="#the-experience">Explore</a> ·
  <a href="#start-here">Run locally</a> ·
  <a href="#system-design">Architecture</a> ·
  <a href="#what-we-found">Findings</a> ·
  <a href="#why-mariadb-and-neo4j">MariaDB + Neo4j</a> ·
  <a href="#project-guide">Documentation</a>
</p>

![CiteHop search workspace with charcoal surfaces, lime accents, sample questions, and links to the library and graph.](assets/readme/workspace-desktop.png)

<p align="center"><sub>Actual application screenshot · <a href="assets/readme/workspace-mobile.png">See the mobile layout</a> · Built by Danial and Akshat for the Databases course at Constructor University.</sub></p>

## Why CiteHop

An answer is more useful when you can inspect the evidence behind it. CiteHop is a local research app over a pinned collection of **100 English Wikipedia articles about machine learning**. It retrieves passages with MariaDB, generates answers with source labels through a local language model, and lets you explore article relationships in Neo4j.

The central database question is concrete: **how does MariaDB’s native vector retrieval compare with keyword search when ordinary relational filters are involved?** The repository includes the implementation, a reproducible evaluation harness, and saved provisional results.

Search, Library, Graph, and Dashboard are implemented. Question labels and answer grounding still need human review before the evaluation supports final claims. This is a course project for local use; authentication and production hosting are outside its scope.

## The experience

| Surface | What you can do |
|---|---|
| **Search** · `/` | Choose Keyword or Meaning retrieval, filter by category, article length, or linking article, then explicitly generate an answer and inspect its cited passages. |
| **Library** · `/library` | Browse articles, inspect source revisions and stored passages, and open their graph neighborhoods. |
| **Graph** · `/graph` | Select and expand articles, inspect categories and directional links, and find bounded paths between sources. |
| **Dashboard** · `/dashboard` | Inspect corpus and graph status, compare saved retrieval runs, review timing and grounding status, and export results. |

The charcoal-and-lime workspace adapts to desktop and mobile, with keyboard navigation, visible focus states, collapsible filters, and expandable sample questions from the dev split. Loading, empty, stale-data, and service-failure states are part of the interface.

| Search: cited answer and ranked sources | Graph: expanded neighborhood and a two-link path |
|---|---|
| ![Search view: an answer citing S1 above five ranked passages from MariaDB vector search](docs/screenshots/search-answer-1440.png) | ![Graph view: an expanded Neo4j neighborhood with a highlighted path and the inspector](docs/screenshots/graph-path-1440.png) |
| **Dashboard: live counts and a saved run** | **Library: the pinned collection** |
| ![Dashboard view: corpus and graph counts, Recall@5 and latency of the saved run](docs/screenshots/dashboard-1440.png) | ![Library view: article cards with categories](docs/screenshots/library-1440.png) |

<sub>Captured by `make e2e` on real data from a clean setup (corpus:1, 1,776 chunks). More, including the citation inspector and 390 px views, in [`docs/screenshots/`](docs/screenshots/).</sub>

**Try the flow:** ask a question → find sources → generate an answer → inspect a citation → explore connections.

- Retrieval and generation are separate actions. Clicking a sample question only retrieves sources.
- Answers use at most five passages, an **estimated** 1,800-token context budget, and a 300-token output cap. Citation labels are validated; a valid label alone does not establish grounding.
- The graph follows Wikipedia article links and categories. A link is not evidence that two articles agree.
- Graph exploration defaults to one hop, 50 nodes, and 100 edges; limits are two hops, 100 nodes, and 200 edges. Article paths use at most three links.

## Start here

### 1. Install prerequisites

Use the versions pinned by this repository:

| Requirement | Version / purpose |
|---|---|
| Node.js / npm | **26.12.1 / 11.20.0**; see [`.node-version`](.node-version) and [`frontend/package.json`](frontend/package.json) |
| Python | **3.11**; see [`.python-version`](.python-version) |
| uv | Python environment and locked dependencies |
| Docker with Compose | MariaDB **11.8.9** and Neo4j Community **5.26.32** |
| MariaDB Connector/C | Native dependency for the Python connector |
| Ollama | Optional for cited answer generation; retrieval works without it |

On macOS, install the native prerequisites with Homebrew, and install the pinned Node version separately:

```sh
brew install python@3.11 mariadb-connector-c uv
# Apple Silicon; use your Homebrew prefix on other systems.
export PATH="/opt/homebrew/opt/mariadb-connector-c/bin:$PATH"
```

On Linux, install Python 3.11, a C build toolchain, MariaDB development headers, and uv through your system’s package setup.

### 2. Set up the local stack

```sh
git clone https://github.com/danialeyz/citehop.git
cd citehop
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Edit root `.env` to choose local database passwords and a `COMPOSE_PROJECT_NAME` unique to your checkout, then run:

```sh
make venv-ml frontend-install
make db-up
make check
make sql FILE=sql/corpus_schema.sql
```

`make venv-ml` installs the locked runtime, development tools, and ML dependencies needed for embeddings and Meaning search. `make venv` installs without the ML extra and removes it from an existing environment. Dependency versions live in [`pyproject.toml`](pyproject.toml), `uv.lock`, and `frontend/package-lock.json`.

### 3. Load and prepare the corpus

```sh
# Fetch the revisions pinned in eval/corpus.json.
.venv/bin/python -m citehop.acquire fetch --subset full
.venv/bin/python -m citehop.corpus --snapshot data/wikipedia/full.json

# Create passage embeddings, then build the graph projection.
make embed
make graph-import
make embed-status graph-status
```

The first embedding run downloads the pinned `BAAI/bge-base-en-v1.5` model into the Hugging Face cache. Acquisition downloads missing Wikipedia revisions and checks their hashes; it does not silently replace pinned content. If a revision’s rendered content has changed, see the [acquisition and cache instructions](eval/README.md).

For a smaller first run, fetch `--subset smoke`, load `data/wikipedia/smoke.json`, and use `make embed-smoke` before importing the graph. **Loading a snapshot reconciles the whole corpus:** loading smoke after full removes the other 90 articles. Keep the full dataset for the saved evaluation’s question set.

### 4. Start the app

In two terminals, from the repository root:

```sh
# Terminal 1
make api

# Terminal 2
make frontend
```

| Local service | Address |
|---|---|
| **CiteHop** | **http://127.0.0.1:3000** |
| API documentation | http://127.0.0.1:8000/docs |
| API health | http://127.0.0.1:8000/api/v1/health |
| Neo4j Browser | http://127.0.0.1:7474 |

Try **“Who coined the term machine learning?”**, choose a retrieval method, and select **Find sources**. The Library and Graph should now reflect your loaded snapshot.

### 5. Enable cited answers (optional)

Start Ollama and pull the model configured by `CITEHOP_GENERATOR_MODEL` in root `.env`. The example configuration uses:

```sh
ollama serve  # if the Ollama app is not already running
# In another terminal:
ollama pull hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS
```

This model is about **14 GB on disk** and needs sufficient local resources. Set `OLLAMA_HOST` and `CITEHOP_GENERATOR_MODEL` in root `.env`, then restart the API if you changed them. No model API key is required. Select **Generate answer** after retrieving sources; source passages remain available if generation fails. See [generation limits and validation](docs/RAG.md).

### Local configuration and troubleshooting

| Situation | What to check |
|---|---|
| UI reports API unreachable | Start `make api`; check `API_UPSTREAM` in `frontend/.env.local`, then restart Next.js. |
| API health returns 200 but a database is unavailable | Health reports API liveness separately from `services.mariadb` and `services.neo4j`; run `make db-up` and `make check`. |
| Library is empty | Apply the schema and load a corpus snapshot in steps 2–3. |
| Meaning search lacks embeddings | Run `make venv-ml`, `make embed`, and `make embed-status`; restart the API after installing dependencies. |
| Graph is stale or missing | Run `make graph-import` after loading a changed corpus, then `make graph-status`. |
| Port already in use | Override API/frontend ports as below; database ports are configured in root `.env`. |

```sh
make api API_PORT=8001
# Set API_UPSTREAM=http://127.0.0.1:8001 in frontend/.env.local.
make frontend FRONTEND_PORT=3001
```

Next.js proxies `/api/*` to FastAPI and uses the same upstream for server-side requests. Database and model settings belong in root `.env`, never `NEXT_PUBLIC_*`. For database port changes, update `DB_PORT`, `NEO4J_BOLT_PORT`, and `NEO4J_HTTP_PORT`; `NEO4J_URI` must match the Bolt port.

Docker runs the databases; the API and frontend run on the host. `make db-down` preserves named volumes. Changing password variables does not change credentials already stored in an existing volume, and Compose `down -v` deletes its persisted data.

## System design

**One frontend. One Python API. Two databases with distinct responsibilities.**

```mermaid
flowchart TB
    subgraph CLIENT["Research workspace · Next.js"]
        SEARCH[Search]
        LIB[Library]
        EXPLORER[Graph explorer]
        DASH[Dashboard]
    end
    subgraph SERVER["Application boundary · FastAPI"]
        API[Validated HTTP requests]
        RET[Retrieval + SQL filters]
        RAG[Evidence resolution + citation validation]
        NAV[Bounded graph queries]
        EVAL[Saved-run reader]
        API --> RET & RAG & NAV & EVAL
    end
    SEARCH & LIB & EXPLORER & DASH -->|/api/v1| API
    RET --> SQL[(MariaDB)]
    RAG -->|exact passages| SQL
    RAG -->|explicit generation| MODEL[Local Ollama]
    NAV --> NEO[(Neo4j)]
    EVAL --> RUNS[Versioned JSON artifacts]
    SQL -. manual snapshot import .-> NEO
    classDef app fill:#1a1d18,stroke:#c6f27b,color:#f0f2e9
    classDef store fill:#2b3820,stroke:#c6f27b,color:#f0f2e9
    class SEARCH,LIB,EXPLORER,DASH,API,RET,RAG,NAV,EVAL,MODEL,RUNS app
    class SQL,NEO store
```

| Layer | Implementation |
|---|---|
| Interface | Next.js App Router, React, TypeScript, Tailwind CSS |
| Graph and charts | React Flow and Recharts |
| API | FastAPI and Pydantic; generated OpenAPI types for the frontend |
| Retrieval | MariaDB `FULLTEXT` and native cosine search over `VECTOR(768)` |
| Embeddings | Pinned `BAAI/bge-base-en-v1.5`, 300-token windows with 50-token overlap |
| Graph | Neo4j Community, derived from versioned article links and categories |
| Generation | Local Ollama, bounded context, explicit source labels |
| Evaluation | Frozen dev/test questions, raw ranks, timings, manifests, and review fields |

MariaDB is the source of truth. Neo4j is a rebuildable projection, so graph outages do not prevent MariaDB retrieval. Version checks keep stale graph data from being presented as current.

**Filtered vector queries intentionally use exact cosine scans.** On the pinned MariaDB version, applying filters to indexed candidates can miss eligible passages. CiteHop applies SQL filters before the result limit; unfiltered vector retrieval can use the native HNSW index. See the [query plans and retrieval rationale](docs/RETRIEVAL.md).

### From pinned articles to searchable evidence

Preparation happens explicitly. Embedding runs resume completed work; graph import validates a snapshot before marking it ready.

```mermaid
flowchart LR
    W["Pinned Wikipedia revisions"] --> C["Fetch + verify hashes"]
    C --> CACHE["Local revision cache"]
    CACHE --> LOAD["Transactional corpus load"]
    LOAD --> SQL[("MariaDB articles + links")]
    SQL --> CHUNK["Exact text spans<br/>300 tokens / 50 overlap"]
    CHUNK --> BGE["Pinned BGE model"]
    BGE --> VEC[("Chunks + VECTOR(768)")]
    SQL --> IMPORT["Manual graph import"]
    IMPORT --> VALIDATE["Validate nodes, edges, revisions"]
    VALIDATE --> NEO[("Versioned Neo4j graph")]
    classDef step fill:#1a1d18,stroke:#c6f27b,color:#f0f2e9
    class W,C,CACHE,LOAD,SQL,CHUNK,BGE,VEC,IMPORT,VALIDATE,NEO step
```

### How a query chooses its retrieval path

Keyword search uses FULLTEXT. Meaning search embeds the query once, then selects an indexed or exact path according to the eligible corpus. All paths return ranked passages with source metadata.

```mermaid
flowchart TB
    Q["Question + relational filters"] --> M{Search method}
    M -->|Keyword| K["FULLTEXT relevance<br/>SQL predicates before LIMIT"]
    M -->|Meaning| B["BGE query embedding"]
    B --> F{"Filters or mixed<br/>embedding configurations?"}
    F -->|No| ANN["Native HNSW vector index"]
    F -->|Yes| EXACT["Exact cosine over eligible rows<br/>IGNORE INDEX"]
    K & ANN & EXACT --> R["Rank + limit passages"]
    R --> S["Join article metadata<br/>Return sources + timings"]
    classDef step fill:#1a1d18,stroke:#c6f27b,color:#f0f2e9
    class Q,M,K,B,F,ANN,EXACT,R,S step
```

### From retrieved passages to a cited answer

The browser sends chunk IDs and the corpus version. The API resolves the actual evidence; it does not trust passage text supplied by the browser.

```mermaid
sequenceDiagram
    actor Reader
    participant UI as Research workspace
    participant API as FastAPI
    participant DB as MariaDB
    participant LLM as Local Ollama
    Reader->>UI: Find sources
    UI->>API: POST /api/v1/search
    API->>DB: Ranked retrieval with SQL filters
    DB-->>API: Passages + source metadata
    API-->>UI: Sources + corpus version + timings
    Reader->>UI: Generate answer
    UI->>API: POST /api/v1/answer (chunk IDs + version)
    API->>DB: Check version and resolve exact passages
    alt Missing chunks or changed corpus
        API-->>UI: Reject stale or missing evidence
    else Current evidence
        API->>API: Select whole passages within context budget
        alt No usable passage
            API-->>UI: Insufficient evidence (no model call)
        else Context available
            API->>LLM: Question + bounded context + source labels
            LLM-->>API: Answer or abstention
            API->>API: Validate citation labels and status
            API-->>UI: Answer status + sources + citation mapping
        end
    end
    Reader->>UI: Open a citation
    UI-->>Reader: Exact supporting passage + source link
```

### Data model

The installed schema is [`sql/corpus_schema.sql`](sql/corpus_schema.sql):

| Table | Stores |
|---|---|
| `articles` | Wikipedia page and revision identity, source text, URLs, hashes, and attribution |
| `chunks` | Exact passage spans, deterministic IDs, configuration hashes, and 768-dimensional vectors |
| `article_categories` | Category membership by exact name |
| `article_links` | Directed links between corpus articles |
| `embedding_configs` | Reproducible chunking and embedding settings |
| `corpus_versions` | Loaded snapshot identity and counts |

The relationships below use actual schema names; fields are abbreviated. `embedding_config` is an application-level association, not a declared SQL foreign key, and `corpus_versions` tracks snapshots rather than individual article rows.

```mermaid
erDiagram
    articles ||--o{ chunks : "current revision contains"
    articles ||--o{ article_categories : "belongs to"
    articles ||--o{ article_links : "source of"
    articles ||--o{ article_links : "target of"
    articles {
        int article_id PK
        bigint revision_id
        string title
        string revision_url
        text text
        string text_sha256
    }
    chunks {
        string chunk_id PK
        int article_id FK
        bigint revision_id FK
        int char_start
        int char_end
        text text
        vector embedding "768 dimensions"
        string embedding_config
    }
    article_categories {
        int article_id PK,FK
        string category_name PK
    }
    article_links {
        int source_article_id PK,FK
        int target_article_id PK,FK
    }
    embedding_configs {
        string embedding_config PK
        string chunk_config
        json config_json
    }
    corpus_versions {
        int version_id PK
        string content_sha256
        string source_corpus_id
        string subset
    }
```

Neo4j projects article nodes, category nodes, `LINKS_TO`, and `IN_CATEGORY` relationships. It does not infer agreement or scholarly citations. See the [data model](docs/DATA_MODEL.md) and [graph documentation](docs/GRAPH.md) for constraints and import behavior.

### Model, chunk, and index choices

| Choice | Setting | Why |
|---|---|---|
| Embedding model | `BAAI/bge-base-en-v1.5` @ `a5beb1e3…`, 768 dimensions, `[CLS]` pooling, L2-normalized | Strong English retrieval model at base size, MIT license, ~440 MB, runs on a laptop CPU: the full corpus embeds in ~100 s of model time and a query in ~15 ms. One model serves passages (`"{title}\n\n{passage}"`) and queries (with BGE's retrieval instruction); no GPU or API key. |
| Model limit | 512 tokens, `truncation=False` | Nothing is cut silently; an over-long input raises. The longest real input is 310 tokens. |
| Chunks | 300 tokenizer tokens, 50 overlap, word-start boundaries | Long enough for a definition with its context, short enough that five passages fit the 1,800-token answer budget; the overlap keeps a sentence that straddles a boundary whole in one chunk. An initial project choice, not a tuned optimum: 1,776 chunks, 3–59 per article. |
| Vector index | `VECTOR INDEX … M=16 DISTANCE=cosine` | Cosine matches normalized BGE vectors. `M=16` (server default 6) costs little at 1,776 rows and helps recall. |
| Search depth | `mhnsw_ef_search` = 20 (default) | Kept because ANN and exact search returned identical top 5 chunks on every unfiltered dev question (finding 1 below). |
| Filtered queries | `IGNORE INDEX`, exact cosine over eligible rows | In 11.8.9 the index applies `WHERE` after its bounded candidate list, so a filtered indexed query can silently return too few rows. |

Every setting behind a vector (model revision, input format, library versions, device) is hashed into `embedding_config`, so any change produces new rows instead of mixing vector spaces. Details: [embeddings](docs/EMBEDDINGS.md), [retrieval and query plans](docs/RETRIEVAL.md).

A filtered semantic query as CiteHop runs it (simplified from [`citehop/search.py`](citehop/search.py); runnable variants with `EXPLAIN` in [`sql/search_examples.sql`](sql/search_examples.sql)):

```sql
SELECT r.chunk_id, r.article_id, a.title, a.source_url, r.text, 1 - r.distance AS score
FROM (
  SELECT c.chunk_id, c.article_id, c.revision_id, c.text,
         VEC_DISTANCE_COSINE(c.embedding, VEC_FromText(?)) AS distance
  FROM chunks c IGNORE INDEX (vx_chunks_embedding)
  WHERE c.embedding_config = ?
    AND EXISTS (SELECT 1 FROM article_links l              -- linked from article X
                WHERE l.source_article_id = ? AND l.target_article_id = c.article_id)
    AND EXISTS (SELECT 1 FROM articles la                  -- article length
                WHERE la.article_id = c.article_id AND la.length_chars <= ?)
  ORDER BY distance, c.chunk_id
  LIMIT 5
) r
JOIN articles a ON a.article_id = r.article_id AND a.revision_id = r.revision_id
ORDER BY score DESC, r.chunk_id;
```

### What the database-native approach gave us

- **One statement.** Semantic ranking, category / length / link predicates, and the join to article metadata are one SQL query, evaluated before `LIMIT`. With a separate vector store we would filter a global top-k in Python, which silently drops results, or copy every filterable attribute into that store.
- **One transaction, one source of truth.** A chunk and its vector are written together; re-embedding replaces an article's rows in one transaction; the `(article_id, revision_id)` foreign key rejects vectors of a revision that is no longer loaded. There is no second store to sync, back up, or reconcile.
- **Fair baselines.** FULLTEXT, ANN, and exact cosine run over the same rows, so comparisons isolate the method.
- **What it did not give us:** filtered queries cannot use the vector index in 11.8.9. At 1,776 rows the exact scan is cheap; at millions of rows it would not be.

### Two kinds of graph relationship

This is a structural example, not a claim about particular corpus articles. Path finding follows article links only; shared categories do not create path shortcuts.

```mermaid
flowchart LR
    A["Article A"] -->|LINKS_TO| B["Article B"]
    B -->|LINKS_TO| C["Article C"]
    A -. IN_CATEGORY .-> K(["Category"])
    C -. IN_CATEGORY .-> K
    classDef article fill:#1a1d18,stroke:#c6f27b,color:#f0f2e9
    classDef category fill:#332d20,stroke:#e9c780,color:#f0f2e9
    class A,B,C article
    class K category
```

### Graph freshness is a state, not an assumption

Imports rebuild in place. An interrupted import stays `rebuilding`; neighborhood and path queries are served only in `ready`. Source-version checks may be cached for up to five seconds.

```mermaid
stateDiagram-v2
    [*] --> unavailable: No imported graph
    unavailable --> rebuilding: Start explicit import
    rebuilding --> rebuilding: Interrupted or invalid import, retry
    rebuilding --> ready: Validate and record matching version
    ready --> stale: Corpus changes or source version cannot be read
    stale --> ready: Source becomes readable and versions match
    stale --> rebuilding: Reimport current corpus
    ready --> unavailable: Neo4j unreachable
    stale --> unavailable: Neo4j unreachable
    rebuilding --> unavailable: Neo4j unreachable
    unavailable --> ready: Service returns, complete matching snapshot
    unavailable --> stale: Service returns, complete old snapshot
    unavailable --> rebuilding: Service returns, incomplete import
```

## Why MariaDB and Neo4j

**MariaDB demonstrates the assignment:** native vectors, SQL-filtered semantic retrieval, joins, and measured recall and latency. Search, answers, the Library, and the Dashboard's corpus numbers need MariaDB only, and they keep working when Neo4j is down (checked in C14).

**Neo4j powers derived relationship exploration:** bounded neighborhoods (one hop by default, two at most, 100 nodes / 200 edges hard caps) and shortest paths of at most three article links, with transaction timeouts. It is a projection of `article_links` and `article_categories` rebuilt by `make graph-import`; it stores no embeddings and serves no search.

**Extra cost**, measured on the demo machine ([details](docs/SUBMISSION.md#cost-of-the-second-database)):

| | MariaDB | Neo4j |
|---|---|---|
| Container memory | 0.13–0.18 GiB | 0.58–0.73 GiB (heap capped at 512 MB, page cache 256 MB) |
| Data volume | 234 MB: text, chunks, vectors, indexes | 541 MB: 556 nodes, 2,018 edges, store files and logs |
| Operations | — | an explicit import after every corpus change (2 s here), one more service, port, and password |

**Snapshot consistency limitations.** No transaction spans both databases, and nothing syncs in the background. The import records the MariaDB `corpus_versions` ID it copied; when MariaDB moves on, the graph reports `stale` (within the five-second cache) and refuses traversal until reimported. Rebuilds happen in place, so a graph that is `rebuilding` has no current snapshot, and a failed import stays `rebuilding`. Version IDs count loads in one database: the same content is `corpus:1` on a fresh load and `corpus:2` where smoke was loaded first, so compare `content_sha256` across machines.

The brief does not say whether a second database is acceptable, so Neo4j is disclosed here and the MariaDB demonstration stands without it.

## What we found

Run [`20261031T174404Z-dev-test-15b1f5a1`](results/runs/20261031T174404Z-dev-test-15b1f5a1/manifest.json), recorded during the C14 clean-setup reproduction: Apple M6, 24 GB, MariaDB 11.8.9 in local Docker, 100 articles, 1,776 chunks, 10 dev and 20 test questions. The earlier [development run](results/runs/20261031T162301Z-dev-test-15b1f5a1/manifest.json) on identical content (same `content_sha256` and config) gave the same recall. Where every figure comes from: [SUBMISSION.md](docs/SUBMISSION.md#where-the-numbers-come-from).

> [!WARNING]
> **Provisional.** All 30 question labels were drafted by an AI agent and are unreviewed, and none of the 10 saved answers has a grounding review (`final_claims_allowed: false`). These are harness results, not final quality claims; the Dashboard shows the same review states.

**Recall@5**, article-level after deduplicating chunk hits, answerable questions only (unanswerable ones are reported separately):

| Split | Keyword (FULLTEXT) | Vector (HNSW) | Exact cosine |
|---|---|---|---|
| dev, 8 answerable | 0.958 | 1.000 | 1.000 |
| test, 17 answerable | 0.959 | 0.976 | — |
| test, unfiltered (12) / filtered (5) | 0.942 / 1.000 | 0.967 / 1.000 | — |

**Latency**, test split unless noted, ms, median / nearest-rank p95 over every timed call (3 repetitions), Python client round trip included:

| Stage | n | Median | p95 |
|---|---|---|---|
| Keyword retrieval | 54 | 7.8 | 17.4 |
| Vector retrieval, unfiltered (HNSW index) | 38 | 10.3 | 22.2 |
| Vector retrieval, filtered (exact scan of eligible rows) | 16 | 42.2 | 82.8 |
| Exact cosine, unfiltered, dev (no index) | 7 | 218.6 | 303.9 |
| Query embedding (BGE on CPU) | 54 | 15.3 | 30.5 |
| Answer generation (local Ollama) | 10 | 2,171 | 2,665 |

1. **The HNSW index lost nothing here.** On dev, ANN and exact search returned the same top 5 chunks for all 7 unfiltered questions at the default `ef_search` 20, and the indexed query was 10–20× faster (dev medians 9–20 ms vs 185–219 ms across the two runs). On isotropic random vectors, the worst case, the same index needed `ef_search` ≈ 400 for 0.996 overlap ([RETRIEVAL.md](docs/RETRIEVAL.md#indexed-vs-exact-retrieval)), so this depends on real embeddings clustering.
2. **Filters and the vector index interact.** Filtered vector queries run as an exact scan over the rows the SQL predicate admits (see the choices above). That is correct and still fast at this size, but it is a linear scan.
3. **Meaning beats keywords slightly.** Vector search fell short on one test question (3 of 5 relevant articles); keyword search fell short on two test questions and one dev question. Every filtered question reached 1.0, but there are only 5 on test and 2 on dev.
4. **Bounded answers behave as designed.** 7 of 7 answerable review questions were answered with valid citation labels and 3 of 3 unanswerable ones abstained. Whether the cited passages support the claims is not yet reviewed.

Latency differs between the two runs (the C14 run shared the laptop with the embedding job, API, and browser); treat it as a spread on one machine, not a benchmark. A 100-article corpus validates the method; it does not establish performance at scale.

**Known gaps.** The brief's "edited since that date" predicate is not offered as a filter, although `articles.revision_timestamp` is stored. Hidden Wikipedia maintenance categories are stored as ordinary categories; the graph view hides them by name pattern. Concurrent users and large corpora were not tested.

```mermaid
flowchart TB
    Q["Frozen questions + corpus/config identity"] --> DEV["Dev · 10 questions"]
    Q --> TEST["Test · 20 questions"]
    DEV --> COMPARE["Keyword vs vector vs exact<br/>Recall + ANN/exact overlap"]
    TEST --> RETRIEVE["Keyword vs vector<br/>Recall + separate timing groups"]
    TEST --> ANSWERS["10 generated answers<br/>Sources + citation mappings"]
    COMPARE & RETRIEVE & ANSWERS --> SAVE["Run manifest + raw retrieval + answers"]
    SAVE --> DASH["Dashboard: measurements + review status"]
    SAVE --> REVIEW["Human review of labels and grounding"]
    REVIEW --> CLAIMS["Qualify conclusions against reviewed evidence"]
    classDef step fill:#1a1d18,stroke:#c6f27b,color:#f0f2e9
    class Q,DEV,TEST,COMPARE,RETRIEVE,ANSWERS,SAVE,DASH,REVIEW,CLAIMS step
```

Run `make eval` against a prepared full corpus, with ML dependencies and Ollama available. This performs generation calls and writes a new run under `results/runs/`. Read the [evaluation protocol and provisional findings](docs/EVALUATION.md) and [human review checklist](eval/README.md) before interpreting or publishing results.

## Development and verification

```sh
make help                         # available targets
make test lint                    # backend unit checks; no databases required
make frontend-check               # lint, types, unit tests, production build
make check                        # live database connectivity and vector check
make api-types                    # regenerate API contract and frontend types
make test-model                   # real tokenizer/model tests; downloads weights
make rag-validate                 # live search and generation validation
make e2e                          # browser journey: search → answer → citation → graph → dashboard
```

`make e2e` ([`frontend/e2e/journey.mjs`](frontend/e2e/journey.mjs), Playwright) needs the API, a production frontend (`npm --prefix frontend run build && npm --prefix frontend run start`), the prepared corpus, an imported graph, and Ollama; it makes one generation call and writes screenshots to `.context/e2e/`. Run `npx --prefix frontend playwright install chromium` once. Use `make e2e FRONTEND_PORT=3001` for another port.

Database integration tests need disposable test instances: `CITEHOP_TEST_DB_NAME=citehop_test .venv/bin/python -m pytest -m db` uses a separate database on the configured server (grant the app user rights on it first). `make test-graph` uses `CITEHOP_TEST_NEO4J_URI` and `CITEHOP_TEST_NEO4J_PASSWORD` and clears the test graph’s CiteHop namespace.

Use `npm ci` and the locked uv environment for installs. `make locks` intentionally refreshes Python locks and exports after dependency edits; commit lockfiles with those changes.

<details>
<summary><strong>Repository layout</strong></summary>

```text
frontend/         Search, Library, Graph, Dashboard; typed API client
citehop/          Acquisition, corpus loading, embeddings, retrieval, RAG, evaluation
  api/            FastAPI routes and request/response schemas
  graph/          Neo4j import, status, neighborhoods, and paths
docker/           Local MariaDB and Neo4j services
sql/              Corpus schema, smoke queries, retrieval examples
eval/             Pinned article manifest and frozen draft question set
results/          Saved evaluation runs and validation evidence
scripts/          API smoke checks, persistence checks, validation helpers
tests/            Backend unit and integration tests
assets/readme/    Application screenshots and historical concept illustrations
docs/             Architecture, subsystem guides, course plan, design references
```

</details>

## Project guide

| Document | Use it for |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Service ownership, API boundaries, and failure behavior |
| [Corpus and questions](eval/README.md) | Pinned revisions, cache recovery, attribution, label review |
| [Data model](docs/DATA_MODEL.md) | Schema, constraints, loading, and versioning |
| [Embeddings](docs/EMBEDDINGS.md) | Model configuration, chunking, resumable embedding runs |
| [Retrieval](docs/RETRIEVAL.md) | SQL filtering, index behavior, query plans |
| [Cited answers](docs/RAG.md) | Generator configuration, limits, citation validation |
| [Graph](docs/GRAPH.md) / [Graph explorer](docs/GRAPH_EXPLORER.md) | Import and freshness, visual exploration and bounds |
| [API](docs/API.md) | Endpoint contract, errors, and typed client |
| [Evaluation](docs/EVALUATION.md) | Measurement protocol, saved runs, provisional findings |
| [Submission record](docs/SUBMISSION.md) | Clean reproduction log, checks, evidence trail, assignment checklist, open items |
| [Demo script](docs/DEMO.md) | Five-minute walkthrough for reviewers |
| [UI specification](docs/design/COURSE_UI.md) | Product flows and acceptance criteria |
| [Course plan](docs/COURSE_TASKS.md) / [Agent prompts](docs/AGENT_PROMPTS.md) | Task scope, dependencies, and implementation guidance |

The live theme is defined in [`frontend/app/globals.css`](frontend/app/globals.css). Older design mockups and concept illustrations are historical references, not screenshots or sources of corpus facts.

## Course, sources, and credits

**Databases · Constructor University · Team: Danial and Akshat.** The implementation was built with AI coding agents working from the task cards in [docs/COURSE_TASKS.md](docs/COURSE_TASKS.md); the question set was drafted by an agent and still needs the team's review. CiteHop follows area 4, “Vector search and RAG, natively,” of the [MariaDB student project brief](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively).

Wikipedia text is attributed to its contributors, with pinned revision, history, and license URLs recorded during acquisition; see [provenance and attribution](eval/README.md#provenance-and-attribution). The corpus cache and model weights are downloaded separately. Saved evaluation artifacts include source passages and review metadata. Article text is from English Wikipedia under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The embedding model is [`BAAI/bge-base-en-v1.5`](https://huggingface.co/BAAI/bge-base-en-v1.5) (MIT); model configuration and revision are documented in the [embedding guide](docs/EMBEDDINGS.md). Answers use [Qwen3.6-35B-A3B GGUF by Unsloth](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) through Ollama. MariaDB [vector documentation](https://mariadb.com/docs/server/reference/sql-structure/vectors).

<p align="center"><strong>Every answer has a source. Every hop has a boundary.</strong></p>
