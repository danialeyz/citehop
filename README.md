<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="CiteHop — search, cite, explore" width="480">
  </picture>
</p>

<p align="center"><strong>Ask a question. Follow the sources.</strong><br>Native vector search. Answers with citations. A knowledge graph you can explore.</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-architecture_%26_design-77e4f0?style=flat-square" alt="Status: architecture and design">
  <img src="https://img.shields.io/badge/course-Databases-4338ca?style=flat-square" alt="Databases course">
  <img src="https://img.shields.io/badge/university-Constructor-0d9488?style=flat-square" alt="Constructor University">
</p>

<p align="center"><sub>A <strong>Databases course project at Constructor University</strong> · area 4, “<a href="https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively">Vector search and RAG, natively</a>” of the MariaDB student projects</sub></p>

<p align="center">
  <a href="#the-experience">Experience</a> ·
  <a href="#system-design">System design</a> ·
  <a href="#data-model">Data model</a> ·
  <a href="#the-knowledge-graph">Knowledge graph</a> ·
  <a href="#build-roadmap">Roadmap</a> ·
  <a href="#start-here">Start here</a>
</p>

![CiteHop: from source articles to retrieved passages, cited answers, and connected knowledge.](assets/readme/hero.svg)

> [!IMPORTANT]
> **This repository is at the architecture and design stage.** The current deliverables are the task plan, agent prompts, architecture, visual specification, and starter repository. The application, database loaders, API, and measurements are still to be built. All diagrams below describe the intended system; illustrations are concepts, not application screenshots.

## Why CiteHop

A useful answer should lead back to the material behind it. CiteHop is designed to retrieve relevant Wikipedia passages, generate a short answer with traceable citations, and let the reader explore the articles connected to those sources.

The database question is concrete: **how well does MariaDB's native vector search retrieve relevant sources when combined with ordinary relational filters?** We will compare it with keyword retrieval, measure recall and latency, and show what happens when the evidence is insufficient.

The graph adds a second way to explore: follow real article links and categories, inspect their provenance, and reveal bounded paths between sources. It does not turn a hyperlink into proof that two articles agree.

**Built by Danial and Akshat for the Databases course at Constructor University.**

## The experience

| ⌕ Search | ▤ Library | ◇ Graph | ▥ Dashboard |
|---|---|---|---|
| Ask a question; choose keyword or meaning search. | Browse the loaded article collection. | Explore sources as a connected neighborhood. | Understand the data and measured results. |
| Filter by category, article length, or incoming link source. | Inspect revisions, categories, and exact passages. | Select nodes, expand links, and highlight paths. | Compare recall, latency, and grounding checks. |
| Generate an answer explicitly; open every cited passage. | Open the original article or jump into the graph. | Keep source evidence beside the visualization. | Export a named run with its configuration. |

```mermaid
flowchart LR
    Q[Ask a question] --> S[Find relevant passages]
    S --> A[Generate a cited answer]
    A --> E[Inspect the exact evidence]
    E --> G[Explore connected articles]
    S --> D[Compare measured retrieval]
    classDef action fill:#11273b,stroke:#77e4f0,color:#f1f5f9
    class Q,S,A,E,G,D action
```

The visual direction is a dark research workspace: navy surfaces, cyan highlights, warm category accents, readable typography, and a responsive layout. [See the full UI specification →](docs/design/COURSE_UI.md)

## System design

**One frontend. One Python API. Two databases with distinct responsibilities.**

```mermaid
flowchart TB
    subgraph CLIENT[Presentation]
        WEB[Next.js + React + Tailwind]
        VIEWS[Search / Library / Graph / Dashboard]
        WEB --- VIEWS
    end
    WEB -->|same-origin API proxy| API[FastAPI / validated HTTP contract]
    subgraph APPLICATION[Python application]
        API --> RET[Retrieval + SQL filters]
        API --> GEN[Bounded RAG generation]
        API --> NAV[Graph neighborhoods + paths]
        API --> EVAL[Saved-run reader]
    end
    RET --> DB[(MariaDB: text + metadata + vectors)]
    GEN -->|load cited passages| DB
    GEN --> MODEL[One configured language model]
    NAV --> NEO[(Neo4j: article + category graph)]
    EVAL --> FILES[Versioned JSON / CSV results]
    DB -. explicit snapshot import .-> NEO
    classDef store fill:#123a42,stroke:#77e4f0,color:#f1f5f9
    classDef app fill:#14243b,stroke:#6487ad,color:#f1f5f9
    classDef external fill:#3c3020,stroke:#eac675,color:#fff5db
    class DB,NEO store
    class WEB,VIEWS,API,RET,GEN,NAV,EVAL app
    class MODEL,FILES external
```

| Component | Selected technology | Responsibility |
|---|---|---|
| Web application | Next.js App Router, React, TypeScript | Routes, interaction state, source inspection |
| Visual system | Tailwind CSS | Shared tokens, responsive layouts, reusable components |
| Graph canvas | React Flow | Custom nodes, stable layouts, selection, expansion |
| Dashboard charts | Recharts | Small comparisons with accessible table alternatives |
| HTTP API | FastAPI, Pydantic | Validated requests, shared application logic, OpenAPI types |
| Corpus and retrieval | MariaDB, native `VECTOR(768)`, FULLTEXT | Canonical documents, embeddings, filters, joins |
| Relationship exploration | Neo4j Community | Derived graph, bounded neighborhoods and paths |
| Embeddings | `BAAI/bge-base-en-v1.5` | One consistent 768-dimensional representation |
| Evaluation | Python, saved JSON/CSV | Reproducible inputs, outputs, timings, review evidence |

React is used through Next.js. Python owns retrieval and generation. The frontend receives data through FastAPI and never connects directly to either database.

### Why both MariaDB and Neo4j?

MariaDB is the source of truth and the focus of the course demonstration. Text, metadata, and embeddings stay together; semantic retrieval applies SQL predicates and joins before the final result limit.

Neo4j is a **rebuildable graph projection** of the same article links and categories. It supports the visual explorer without replacing MariaDB's vector index. The tradeoff is an additional local service and an explicit import step. Search remains usable if the graph is unavailable; graph freshness is visible rather than assumed.

[Architecture decisions, local topology, API routes, and failure behavior →](docs/ARCHITECTURE.md)

## Data model

### Relational source of truth

The following is the **proposed logical schema**, not installed DDL. C03 will finalize column names, types, constraints, and indexes.

```mermaid
erDiagram
    ARTICLES ||--o{ CHUNKS : contains
    ARTICLES ||--o{ ARTICLE_CATEGORIES : belongs_to
    ARTICLES ||--o{ ARTICLE_LINKS : outgoing
    ARTICLES ||--o{ ARTICLE_LINKS : incoming
    ARTICLES {
        bigint article_id PK
        string title
        string canonical_url
        bigint revision_id
        datetime revision_timestamp
        int article_length
        string corpus_version
    }
    CHUNKS {
        string chunk_id PK
        bigint article_id FK
        int sequence_number
        string section_label
        text passage
        vector embedding_768
        string text_hash
        string embedding_config_id
    }
    ARTICLE_CATEGORIES {
        bigint article_id PK,FK
        string category_id PK
        string category_name
    }
    ARTICLE_LINKS {
        bigint source_article_id PK,FK
        bigint target_article_id PK,FK
    }
```

- **Articles** retain source URLs and revision identity so evidence can be traced to a snapshot.
- **Chunks** keep passages and their vectors together. FULLTEXT provides the keyword baseline; a native vector index supports cosine retrieval.
- **Categories and links** support ordinary SQL filters as well as graph import.
- **Evaluation results** live in named JSON/CSV artifacts with manifests; a separate metrics database is unnecessary for this scope.

### Derived property graph

```mermaid
flowchart LR
    A[Article A] -->|LINKS_TO| B[Article B]
    B -->|LINKS_TO| C[Article C]
    A -. IN_CATEGORY .-> K([Category])
    C -. IN_CATEGORY .-> K
    classDef article fill:#11273b,stroke:#77e4f0,color:#f1f5f9
    classDef category fill:#3c3020,stroke:#eac675,color:#fff5db
    class A,B,C article
    class K category
```

These are relationship types, not sample corpus facts. Article IDs match MariaDB; category IDs are canonical. A Wikipedia link is recorded as `LINKS_TO`, never mislabeled as a scholarly citation or inferred similarity.

## From corpus to cited answer

### Prepare once; reuse the evidence

```mermaid
flowchart LR
    W[Wikipedia revisions] --> CACHE[Pinned article manifest + cache]
    CACHE --> SQL[(MariaDB corpus)]
    SQL --> CHUNK[Chunk text: 300 tokens / 50 overlap]
    CHUNK --> EMBED[Embed with one recorded model]
    EMBED --> VEC[(Passages + 768-dimensional vectors)]
    SQL --> IMPORT[Explicit graph import + validation]
    IMPORT --> GRAPH[(Versioned Neo4j projection)]
    classDef data fill:#123a42,stroke:#77e4f0,color:#f1f5f9
    class SQL,VEC,GRAPH data
```

Chunk size and overlap are initial project choices, not measured optima. Ingestion will record tokenizer/model revisions, input formatting, normalization, hashes, and actual token lengths. Changed source text or configuration invalidates stale vectors.

### Retrieve first; generate deliberately

```mermaid
sequenceDiagram
    actor Reader
    participant UI as Next.js
    participant API as FastAPI
    participant DB as MariaDB
    participant LLM as Generator
    Reader->>UI: Question + method + SQL filters
    UI->>API: POST /search
    API->>DB: Retrieve eligible ranked passages
    DB-->>API: IDs, text, metadata, corpus version
    API-->>UI: Source cards + timings
    Reader->>UI: Generate answer
    UI->>API: POST /answer with selected chunk IDs
    API->>DB: Resolve passages and validate version
    DB-->>API: Exact evidence
    alt Evidence available
        API->>LLM: Question + bounded context + citation labels
        LLM-->>API: Answer with source labels
        API-->>UI: Validated citation mapping + answer status
    else Evidence absent or stale
        API-->>UI: Explicit missing/stale evidence status
    end
    Reader->>UI: Open citation and inspect passage
```

Generation uses at most **five passages**, **1,800 context tokens**, and **300 output tokens** per explicit call. The backend loads passages by ID rather than trusting browser-supplied text. Unknown citation labels invalidate the answer; correctly formed citations still require a grounding check. Missing evidence and provider failures are visible states.

## The knowledge graph

![Illustrative knowledge-graph interaction: inspect a source, expand its neighborhood, and follow a bounded path. Not live application data.](assets/readme/graph-concept.svg)

The graph is a core product surface, designed around readable exploration:

| Explore | Understand | Stay oriented |
|---|---|---|
| Pan, zoom, fit view, minimap | Distinct article and category nodes | Stable positions during expansion |
| Expand a selected neighborhood | Directional edges and relation labels | Seed and search-result highlighting |
| Find a path between two articles | Source inspector with exact passages | Breadcrumbs and reset controls |
| Toggle categories and edge types | Snapshot version and provenance | Mobile detail panel and keyboard connection list |

**Exploration bounds:** one hop by default, two maximum; 50 nodes/100 edges by default, with a hard limit of 100/200. Article-to-article paths are limited to three links. The API enforces limits and timeouts; the canvas clearly marks truncated views. “No path within three links” does not mean two articles are unrelated.

### A graph that tells you how fresh it is

```mermaid
stateDiagram-v2
    [*] --> rebuilding: Explicit import
    rebuilding --> ready: Validate and activate snapshot
    rebuilding --> unavailable: Import fails without a complete snapshot
    ready --> stale: Source corpus version changes
    stale --> rebuilding: Explicit reimport
    ready --> unavailable: Graph service unreachable
    unavailable --> ready: Service returns with matching snapshot
    unavailable --> stale: Service returns with old snapshot
    unavailable --> rebuilding: Retry incomplete import
```

An implementation may retain an older complete snapshot during a rebuild. In every case, partial data must not appear current. Stale graph expansion/path queries are disabled; normal MariaDB retrieval continues. There is no claim of cross-database atomicity.

## Measure the result

The target is a small, honest experiment rather than an impressive-looking leaderboard.

| Planned scope | Target |
|---|---|
| Corpus | 100 English Wikipedia articles about machine learning |
| Smoke dataset | 10 articles |
| Ground truth | 30 manually checked questions: 10 dev / 20 test |
| Retrieval comparison | MariaDB FULLTEXT vs native vector retrieval |
| Index check | Indexed vs exact cosine retrieval on dev |
| Main metric | Article-level Recall@5, deduplicated across chunks |
| Timing | Median/p95 retrieval latency; embedding and generation reported separately |
| Grounding review | 10 saved answers checked for support, citations, and abstention |

**No benchmark results have been produced yet.** Unanswerable questions are tracked separately from answerable retrieval cases. Each run will preserve its corpus/configuration, split, raw ranks, timings, machine details, and review status. The dashboard will show “Not measured” and “Not reviewed” until evidence exists.

The experiment must report filtered-query behavior honestly, including when a query plan uses an exact scan. A small corpus is useful for teaching and validation; it does not establish large-scale performance.

## Build roadmap

All implementation cards are currently **pending**. Each has bounded scope, dependencies, relevant inputs, and acceptance checks.

| Stage | Tasks | Deliverable |
|---|---|---|
| 🧱 Foundation | C01–C03 | Local stack, pinned Wikipedia corpus, MariaDB schema |
| 🕸️ Knowledge | C04–C05 | Versioned Neo4j projection, reproducible embeddings |
| 🔎 Retrieval and RAG | C06–C08 | Filtered search, cited answers, measured evaluation |
| 🔌 Application contract | C09 | Validated FastAPI endpoints and typed client |
| 🎨 Product | C10–C13 | Library, polished search, visual graph, dashboard |
| 🎓 Submission | C14 | Reproducible tutorial, screenshots, findings, demo |

Optional after the core: reciprocal rank fusion, graph-assisted retrieval, and one controlled chunk-size comparison. Production hosting, authentication, background synchronization, and large parameter sweeps are outside this course scope.

**[Read all tasks →](docs/COURSE_TASKS.md) · [Copy an agent starting prompt →](docs/AGENT_PROMPTS.md)**

## Start here

You can inspect the repository and begin the implementation plan now:

```bash
git clone https://github.com/danialeyz/citehop.git
cd citehop
```

1. Read the [architecture](docs/ARCHITECTURE.md) and [visual specification](docs/design/COURSE_UI.md).
2. Start with **C01** using its [copy-ready prompt](docs/AGENT_PROMPTS.md#c01--align-the-stack-and-local-development).
3. Follow the dependencies in the [task plan](docs/COURSE_TASKS.md). Keep each agent checkout up to date with completed prerequisites.

> [!NOTE]
> **There is no working app quick start yet.** The current Makefile includes placeholder targets whose referenced Compose files and Python modules are not implemented. C01 will establish verified setup commands, dependency versions, and health checks. Do not treat the historical scripts or mockups as a running service.

Planned local environment: Python 3.11, Node.js with a compatible pinned Next.js release, and Docker/Compose for MariaDB and Neo4j. The frontend and FastAPI will run on the host. Exact versions, resource needs, and runtime commands belong to the verified C01 setup, not guessed installation instructions.

<details>
<summary><strong>Intended project layout</strong> — directories and modules marked “planned” are not implemented yet</summary>

```text
citehop/
├── frontend/            planned: Next.js, React, Tailwind, graph canvas
├── citehop/             package skeleton
│   ├── api/             planned: FastAPI routes and schemas
│   └── ...              planned: ingest, embed, search, rag, graph, evaluate
├── docker/              placeholder: local database services
├── sql/                 placeholder: MariaDB schema
├── scripts/             placeholder: data acquisition tools
├── eval/                planned: questions, labels, review status
├── tests/               placeholder: unit and integration checks
├── results/             placeholder: saved run evidence
├── assets/              logo variants and README illustrations
├── docs/
│   ├── ARCHITECTURE.md  service ownership and contracts
│   ├── COURSE_TASKS.md  14 core tasks + 3 optional tasks
│   ├── AGENT_PROMPTS.md one starting prompt per task
│   └── design/          current UI spec + historical visual references
└── app/                 legacy guidance; frontend work moves to frontend/
```

</details>

## Project guide

| Document | Use it for |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Service boundaries, graph consistency, HTTP contract, limits |
| [Course task plan](docs/COURSE_TASKS.md) | Scope, dependencies, acceptance criteria, evaluation |
| [Agent prompts](docs/AGENT_PROMPTS.md) | Starting one bounded implementation task |
| [Current UI specification](docs/design/COURSE_UI.md) | Search, Library, Graph, Dashboard, visual acceptance |
| [Design system](docs/design/DESIGN_SYSTEM.md) | Existing visual tokens; current UI scope takes precedence |
| [Design instructions](docs/design/AGENT_INSTRUCTIONS.md) | Current guidance and explicitly superseded historical rules |

The older paper-search prototype contains fictional data. It remains a visual reference, not a product screenshot or a source of corpus facts.

## Course, sources, and credits

**Course:** Databases · **University:** Constructor University · **Team:** Danial and Akshat.

CiteHop follows the [MariaDB student project brief, area 4](https://mariadb.org/bachelor_hackathon_2026-09/#4-vector-search-and-rag-natively). The intended submission teaches native vector retrieval through a working, reproducible application with measured findings. Neo4j is an additional exploration layer; the MariaDB demonstration remains self-contained.

Planned source material comes from Wikipedia with recorded page URLs, revisions, and attribution. The embedding model is [BAAI/bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5). Dataset/model terms and attribution will be recorded during acquisition; the repository does not currently bundle the corpus, model weights, or benchmark outputs.

<p align="center">
  <img src="assets/logo-mark.svg" alt="CiteHop hop mark" width="52"><br>
  <strong>Every answer has a source. Every hop has a boundary.</strong><br>
  <sub>A Databases course project at Constructor University.</sub>
</p>
