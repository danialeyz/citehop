# Traps

Things that fail quietly. Each trap has a symptom, a cause and a fix. Add a trap when you lose time to one. The bootstrap list (CITEHOP_BOOTSTRAP.md 5.8) is filled in as the migration phases reach it.

## HNSW WHERE filter returns fewer than k rows

- **Symptom:** a vector query with a `WHERE` clause returns fewer rows than its `LIMIT`, with no error.
- **Cause:** on MariaDB 11.8.9 the vector index returns a bounded candidate list (sized by `mhnsw_ef_search`, default 20). `WHERE` is applied to that list afterwards. Observed on the fixture database with `FORCE INDEX (vx_chunks_embedding) WHERE article_id = X` for an article with 3 chunks: `LIMIT 3` returned 1 row, `LIMIT 5` returned 2, and `LIMIT 50` returned 3. A filtered indexed query filters a global top-k.
- **Fix:** use the index only for unfiltered vector search. Any query with a predicate uses `IGNORE INDEX` and an exact cosine scan over the eligible rows. See [RETRIEVAL.md](RETRIEVAL.md#why-filtered-vector-search-does-not-use-the-hnsw-index).

## FULLTEXT ignores two-letter words

- **Symptom:** `MATCH ... AGAINST('ML')` finds nothing, while `LIKE` or `REGEXP` finds the word.
- **Cause:** InnoDB skips tokens shorter than `innodb_ft_min_token_size` (default 3). The setting only applies when the FULLTEXT index is built, so changing it does not touch an existing index.
- **Fix:** `docker/my.cnf` sets `innodb_ft_min_token_size = 2`. After changing it, rebuild every table that has a FULLTEXT index, for example `ALTER TABLE chunks FORCE`. A full rebuild keeps the vector index in place, so it adds no index after the vector index. In M1, `ML` went from 0 to 20 FULLTEXT hits on `chunks`. CI does not load `my.cnf`, so CI runs with the default.
- **Note:** MariaDB FULLTEXT ranking is not BM25. Call it "MariaDB full-text".

## Docker `lts` or `latest` tag

- **Symptom:** the server version changes after a pull, and results or query plans change with it.
- **Cause:** the `lts` tag moved to 12.3.
- **Fix:** pin `mariadb:11.8.9` in compose and CI. `make check` fails on any other version.
