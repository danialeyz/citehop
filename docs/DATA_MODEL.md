# CiteHop data model (MariaDB)

MariaDB is the source of truth for the corpus. Neo4j (C04) is derived from these tables. Schema: [`sql/corpus_schema.sql`](../sql/corpus_schema.sql). Loader: [`citehop/corpus.py`](../citehop/corpus.py).

## Tables

| Table | Key | Contents |
|---|---|---|
| `articles` | `article_id INT UNSIGNED` (Wikipedia page ID) | Title (unique), pinned `revision_id BIGINT UNSIGNED`, UTC revision timestamp, source/revision URLs, extracted `text MEDIUMTEXT`, `text_sha256`, `length_chars`, `is_smoke`, license URL, attribution line. |
| `article_categories` | (`article_id`, `category_name VARCHAR(255)`) | Category membership as returned by Wikipedia. The canonical category ID is the exact name. |
| `article_links` | (`source_article_id`, `target_article_id`) | Directed internal link between two corpus articles. |
| `chunks` | `chunk_id CHAR(64)` (ASCII, deterministic ID assigned by C05) | Passage of one article revision: `chunk_config`, `ordinal`, character span, `token_count`, `text`, `embedding VECTOR(768) NOT NULL`, `embedding_config`. |
| `corpus_versions` | `version_id INT UNSIGNED` (auto-increment) | One row per distinct loaded content: content SHA-256, C02 `corpus_id`, subset, counts, timestamp. The current version is the highest `version_id`. |

Titles and category names use `utf8mb4_bin`. The server default collation is accent- and case-insensitive, so it would merge distinct Wikipedia names (for example `Machine Learning` and `Machine learning`). Text columns use the default collation so FULLTEXT search ignores case.

## Constraints and indexes

- Foreign keys from categories, links, and chunks to `articles` all use `ON DELETE CASCADE`. Links have both endpoints constrained, so orphan edges cannot exist. A `CHECK` rejects self-links, and the composite primary keys reject duplicate edges and duplicate memberships.
- `chunks (article_id, revision_id)` references `articles (article_id, revision_id)` with `ON UPDATE RESTRICT`. The database therefore refuses to change a revision while chunks of the old revision exist, and it refuses chunks for a revision that is not current.
- Search indexes: `FULLTEXT ft_chunks_text (text)` and `VECTOR INDEX vx_chunks_embedding (embedding) M=16 DISTANCE=cosine`. MariaDB 11.8.9 accepts both and keeps them (`SHOW CREATE TABLE`). `EXPLAIN` of `ORDER BY VEC_DISTANCE_COSINE(...) LIMIT k` uses `vx_chunks_embedding` (`tests/test_corpus_db.py`). `M=16` is above the server default of 6: a larger graph costs little at this corpus size and improves ANN recall. C08 measures recall against the exact baseline.
- Metadata indexes: `articles.length_chars` for length filters, `article_categories (category_name, article_id)` for category filters, `article_links (target_article_id, source_article_id)` for reverse lookups (the primary key already serves linked-from), and `chunks (chunk_config, embedding_config)` for coverage and stale-configuration checks.

Embeddings live on the chunk row because a vector index requires a `NOT NULL` column. C05 inserts each chunk together with its vector. Embedding coverage is therefore the share of articles that have chunks for the active configuration.

## Loading and versioning

```bash
python -m citehop.acquire fetch --subset smoke --offline       # C02: data/wikipedia/smoke.json
python -m citehop.apply_sql sql/corpus_schema.sql              # C01 runner; safe to rerun
python -m citehop.corpus --snapshot data/wikipedia/smoke.json  # or data/wikipedia/full.json
```

The loader checks every record against `eval/corpus.json`: the corpus ID, the pinned revision, the text hash and length, and unique IDs and titles. It accepts only the complete smoke subset or the complete full subset. Links are resolved by exact title within the snapshot. Titles outside the snapshot (other Wikipedia pages, or redirects that were not resolved) are counted as `orphan_links` and are not stored. Duplicate categories and self-links are counted and dropped.

One transaction reconciles the database to the snapshot:

1. Delete chunks of changed revisions and removed articles.
2. Delete obsolete links and categories, then the removed articles.
3. Give renamed articles a temporary title, update changed articles by ID, and insert new ones, in batches of 25 because article text is large. A title can therefore move between page IDs without overwriting another row. Then insert new categories and links in batches of 500.
4. Append a `corpus_versions` row if the content hash differs from the latest row.

Loading the smoke snapshot after the full one removes the other 90 articles. An identical rerun writes nothing, and the version stays the same. Any error rolls back the whole load. Embedding configuration changes are handled by C05 through `chunk_config` and `embedding_config`, not by this version table.

## Measured counts (pinned C02 snapshot `deb00bb7…`, MariaDB 11.8.9, 2026-10-31)

| Subset | Version | Articles | Category rows | Distinct categories | Links | Orphan link titles dropped | Chunks |
|---|---|---|---|---|---|---|---|
| smoke | 1 | 10 | 169 | 119 | 39 | 1,680 | 0 (C05) |
| full | 2 | 100 | 1,101 | 456 | 917 | 7,587 | 0 (C05) |

Each subset was loaded twice. The second run had identical counts, wrote nothing, and kept the version. Article text totals 2,175,082 characters (3,630–70,128 per article). Each load took about 0.3 s wall time on the development Mac.

Known limitation: the stored categories include Wikipedia's hidden maintenance categories (for example `Articles with short description` on all 100 articles). The raw parse output marks them `hidden`, but the C02 record format drops that flag. They should not become graph hubs or filter options until C02 keeps the flag.
