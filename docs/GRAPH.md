# Neo4j graph projection (C04)

Neo4j holds a derived copy of MariaDB's article graph for exploration only. MariaDB stays the source of truth; search never depends on Neo4j. The import is manual — there is no background sync, and no claim that Neo4j and MariaDB change atomically.

## Model

All nodes carry the `CiteHop` namespace label and a stable string `uid`.

| Neo4j | From MariaDB | Properties |
|---|---|---|
| `(:CiteHop:Article)` | `articles` | `uid` = `article:<article_id>`, `article_id`, `title`, `source_url`, `revision_id` |
| `(:CiteHop:Category)` | distinct `article_categories.category` | `uid` = `category:<name>`, `name` |
| `-[:LINKS_TO]->` | `article_links`, both endpoints in `articles` | real outgoing link in the pinned snapshot |
| `-[:IN_CATEGORY]->` | `article_categories` | category membership |
| `(:CiteHopGraphMeta {key: "graph"})` | — | import state, versions, timestamps, counts |

Uniqueness constraints apply only to CiteHop-owned labels: `CiteHop.uid` and `CiteHopGraphMeta.key`. Imports and queries match nodes by `uid`, so other `:Article`/`:Category` data in a shared Neo4j can neither block an import nor be changed by one. Links or memberships that reference missing articles are skipped and counted in the import output. The three source queries live in `citehop/graph/source.py`; their column names follow the shared contract and must be checked against the C03 data model.

## Versioning and import

The source version is a SHA-256 fingerprint of the sorted articles (ID, title, URL, revision), memberships and links, so any revision, link or category change produces a new version.

`make graph-import` (`python -m citehop.graph import`) does an explicit rebuild in place:

1. Marks the graph `rebuilding` with a fresh import ID.
2. Upserts nodes and edges with parameterized `UNWIND … MERGE` batches stamped with that ID. Reruns are idempotent.
3. Deletes CiteHop nodes/edges with an older stamp (changed and deleted records). Nothing outside the `CiteHop` label is touched.
4. Checks Neo4j against the snapshot exactly (article revisions, categories, every link and membership, no duplicates).
5. Only then records the version as complete.

An interrupted or invalid import stays `rebuilding` (with the last error) until a later import succeeds. The previous snapshot is not kept as current.

## Status and queries

`make graph-status` reports `ready`, `stale` (MariaDB version differs or can't be read), `rebuilding`, or `unavailable` (Neo4j unreachable or never imported), plus the source version, imported version, import time and counts. Neighborhood and path queries raise `GraphNotReady` unless the status is `ready`. Any Neo4j failure (connection, auth, missing or starting database, transient fault) is reported as `unavailable`; status never raises.

Computing the source version reads all three MariaDB graph tables. `GraphQueries` caches it for 60 s (`version_ttl`), so a long-lived process such as the API does that read at most once a minute, and a corpus change can take up to 60 s to show as `stale`. Each CLI call is a new process and reads it once. If C03 adds an explicit corpus-version marker, `source_version` should read that instead.

`GraphQueries` in `citehop/graph/queries.py` (CLI: `neighborhood`, `path`):

- **Neighborhood**: 1 hop by default, 2 maximum. Defaults are 50 nodes / 100 edges, with hard caps of 100 / 200. Link and category traversal can be selected separately. Each hop is limited to the remaining node budget, with nodes ordered by `uid`. Edges are returned only when both endpoints are included, and edges touching the seed come first. The result includes `truncated`.
- **Path**: directed by default (undirected is an option, with original edge directions kept). `LINKS_TO` only, at most 3 links, and the lexicographically smallest of the shortest paths. When nothing is found the message is "No path within 3 links".
- Every statement runs with a transaction timeout (default 5 s) and raises `GraphTimeout` if it is exceeded. Connection failures raise `GraphUnavailable`.

## Tests

- `make test`: unit tests, no services needed.
- `make test-graph`: runs against a **disposable** Neo4j and clears the CiteHop namespace there, for example:

```sh
docker run -d --rm --name citehop-neo4j-test -p 127.0.0.1:17687:7687 \
  -e NEO4J_AUTH=neo4j/test-pass neo4j:5.26.32-community
CITEHOP_TEST_NEO4J_URI=bolt://127.0.0.1:17687 CITEHOP_TEST_NEO4J_PASSWORD=test-pass make test-graph
```
