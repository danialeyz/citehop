# Neo4j graph projection (C04)

Neo4j holds a derived copy of MariaDB's article graph for exploration only. MariaDB stays the source of truth; search never depends on Neo4j. The import is manual — there is no background sync, and no claim that Neo4j and MariaDB change atomically.

## Model

All nodes carry the `CiteHop` namespace label and a stable string `uid`.

| Neo4j | From MariaDB | Properties |
|---|---|---|
| `(:CiteHop:Article)` | `articles` | `uid` = `article:<article_id>`, `article_id`, `title`, `source_url`, `revision_id` |
| `(:CiteHop:Category)` | distinct `article_categories.category_name` | `uid` = `category:<name>`, `name` |
| `-[:LINKS_TO]->` | `article_links`, both endpoints in `articles` | real outgoing link in the pinned snapshot |
| `-[:IN_CATEGORY]->` | `article_categories` | category membership |
| `(:CiteHopGraphMeta {key: "graph"})` | — | import state, versions, timestamps, counts |

Uniqueness constraints apply only to CiteHop-owned labels: `CiteHop.uid` and `CiteHopGraphMeta.key`. Imports and queries match nodes by `uid`, so other `:Article`/`:Category` data in a shared Neo4j can neither block an import nor be changed by one. Links or memberships that reference missing articles are skipped and counted in the import output. The source queries live in `citehop/graph/source.py` and follow [DATA_MODEL.md](DATA_MODEL.md). C03's foreign keys and `CHECK`s already reject orphans, duplicates and self-links, so these counts are 0 on a real load.

## Versioning and import

The source version is the latest `corpus_versions.version_id` (shown as `corpus:<id>`). The C03 loader appends a row whenever the loaded content changes. The import reads that version and the three graph tables in one transaction, so the version it records always describes the rows it imported. Snapshots built without MariaDB (tests) fall back to a SHA-256 fingerprint of their content.

`make graph-import` (`python -m citehop.graph import`) does an explicit rebuild in place:

1. Marks the graph `rebuilding` with a fresh import ID.
2. Upserts nodes and edges with parameterized `UNWIND … MERGE` batches stamped with that ID. Reruns are idempotent.
3. Deletes CiteHop nodes/edges with an older stamp (changed and deleted records). Nothing outside the `CiteHop` label is touched.
4. Checks Neo4j against the snapshot exactly (article revisions, categories, every link and membership, no duplicates).
5. Only then records the version as complete.

An interrupted or invalid import stays `rebuilding` (with the last error) until a later import succeeds. The previous snapshot is not kept as current.

## Status and queries

`make graph-status` reports `ready`, `stale` (MariaDB version differs or can't be read), `rebuilding`, or `unavailable` (Neo4j unreachable or never imported), plus the source version, imported version, import time and counts. Neighborhood and path queries raise `GraphNotReady` unless the status is `ready`. Any Neo4j failure (connection, auth, missing or starting database, transient fault) is reported as `unavailable`; status never raises.

Checking the source version is a single `MAX(version_id)` lookup. `GraphQueries` also caches it for 5 s (`version_ttl`), so a burst of API requests costs one lookup, and a corpus change can take up to 5 s to show as `stale`. Failed lookups are not cached.

`GraphQueries` in `citehop/graph/queries.py` (CLI: `neighborhood`, `path`):

- **Neighborhood**: 1 hop by default, 2 maximum. Defaults are 50 nodes / 100 edges, with hard caps of 100 / 200. Link and category traversal can be selected separately. Each hop is limited to the remaining node budget, with nodes ordered by `uid`. Edges are returned only when both endpoints are included, and edges touching the seed come first. The result includes `truncated`.
- **Path**: directed by default (undirected is an option, with original edge directions kept). `LINKS_TO` only, at most 3 links, and the lexicographically smallest of the shortest paths. When nothing is found the message is "No path within 3 links".
- Every statement runs with a transaction timeout (default 5 s) and raises `GraphTimeout` if it is exceeded. Connection failures raise `GraphUnavailable`.

## Measured on the pinned corpus

Pinned C02 snapshot `deb00bb7…`, MariaDB 11.8.9 and Neo4j 5.26.32 Community in throwaway containers, 2026-10-31:

- The full import gave 100 articles, 456 categories, 917 `LINKS_TO` edges and 1,101 `IN_CATEGORY` edges, matching [DATA_MODEL.md](DATA_MODEL.md). A second import deleted nothing and kept the counts. Each run took about 0.3 s wall time.
- A separate check, not using the importer's own validation, compared every article (ID, revision, title), link and membership in Neo4j with MariaDB. They matched exactly.
- Loading the smoke subset made the graph `stale`, and queries were refused. Reimporting deleted 427 nodes and 1,810 edges, leaving 10 / 119 / 39 / 169, which again matched MariaDB. Reloading the full corpus and reimporting restored the full counts.

Known limitation (from C02/C03): hidden Wikipedia maintenance categories are stored as ordinary categories. For example, `Articles with short description` is on all 100 articles, so it becomes a hub. Node and edge caps still bound it, but C12 should not present such categories as topics until C02 keeps the `hidden` flag. The C12 explorer leaves them out by default by matching their names ([GRAPH_EXPLORER.md](GRAPH_EXPLORER.md)).

## Tests

- `make test`: unit tests, no services needed.
- `make test-graph`: runs against a **disposable** Neo4j and clears the CiteHop namespace there, for example:

```sh
docker run -d --rm --name citehop-neo4j-test -p 127.0.0.1:17687:7687 \
  -e NEO4J_AUTH=neo4j/test-pass neo4j:5.26.32-community
CITEHOP_TEST_NEO4J_URI=bolt://127.0.0.1:17687 CITEHOP_TEST_NEO4J_PASSWORD=test-pass make test-graph
```
