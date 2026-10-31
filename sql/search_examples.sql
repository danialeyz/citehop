-- C06 retrieval examples: the same SQL shapes that citehop/search.py builds.
-- Run: python -m citehop.apply_sql sql/search_examples.sql   (needs loaded, embedded chunks)
-- Each example prints its EXPLAIN plan, then its rows. Observed plans: docs/RETRIEVAL.md.
-- The application binds the query vector as VEC_FromText(?) from the embedder; to stay runnable
-- in plain SQL, these examples reuse the first stored chunk of 'Perceptron' as the query vector.
SET @q = (SELECT c.embedding FROM chunks c JOIN articles a ON a.article_id = c.article_id
          WHERE a.title = 'Perceptron' ORDER BY c.ordinal LIMIT 1);

-- 1. Keyword: FULLTEXT natural-language relevance (not BM25), category filter before LIMIT.
EXPLAIN SELECT h.chunk_id, a.title, a.source_url, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             MATCH(c.text) AGAINST('cluster centroids' IN NATURAL LANGUAGE MODE) AS score
      FROM chunks c
      WHERE MATCH(c.text) AGAINST('cluster centroids' IN NATURAL LANGUAGE MODE)
        AND EXISTS (SELECT 1 FROM article_categories ac WHERE ac.article_id = c.article_id
                    AND ac.category_name = 'Cluster analysis algorithms')
      ORDER BY score DESC, c.chunk_id LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;
SELECT h.chunk_id, a.title, a.source_url, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             MATCH(c.text) AGAINST('cluster centroids' IN NATURAL LANGUAGE MODE) AS score
      FROM chunks c
      WHERE MATCH(c.text) AGAINST('cluster centroids' IN NATURAL LANGUAGE MODE)
        AND EXISTS (SELECT 1 FROM article_categories ac WHERE ac.article_id = c.article_id
                    AND ac.category_name = 'Cluster analysis algorithms')
      ORDER BY score DESC, c.chunk_id LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;

-- 2. Vector, unfiltered: ORDER BY the bare cosine distance so the HNSW index serves the top k;
--    article metadata is joined after the LIMIT.
EXPLAIN SELECT h.chunk_id, a.title, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             1 - VEC_DISTANCE_COSINE(c.embedding, @q) AS score
      FROM chunks c
      ORDER BY VEC_DISTANCE_COSINE(c.embedding, @q) LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;
SELECT h.chunk_id, a.title, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             1 - VEC_DISTANCE_COSINE(c.embedding, @q) AS score
      FROM chunks c
      ORDER BY VEC_DISTANCE_COSINE(c.embedding, @q) LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;

-- 3. Vector, filtered (linked from 'Ensemble learning', at most 30,000 characters): exact cosine
--    over the eligible rows. The vector index is ignored on purpose because MariaDB 11.8 would
--    apply these predicates to a bounded HNSW candidate list and could return fewer than k rows.
EXPLAIN SELECT h.chunk_id, a.title, a.length_chars, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             1 - VEC_DISTANCE_COSINE(c.embedding, @q) AS score
      FROM chunks c IGNORE INDEX (vx_chunks_embedding)
      WHERE EXISTS (SELECT 1 FROM articles la WHERE la.article_id = c.article_id
                    AND la.length_chars <= 30000)
        AND EXISTS (SELECT 1 FROM article_links l WHERE l.source_article_id = 22212276
                    AND l.target_article_id = c.article_id)
      ORDER BY VEC_DISTANCE_COSINE(c.embedding, @q), c.chunk_id LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;
SELECT h.chunk_id, a.title, a.length_chars, h.score
FROM (SELECT c.chunk_id, c.article_id, c.revision_id,
             1 - VEC_DISTANCE_COSINE(c.embedding, @q) AS score
      FROM chunks c IGNORE INDEX (vx_chunks_embedding)
      WHERE EXISTS (SELECT 1 FROM articles la WHERE la.article_id = c.article_id
                    AND la.length_chars <= 30000)
        AND EXISTS (SELECT 1 FROM article_links l WHERE l.source_article_id = 22212276
                    AND l.target_article_id = c.article_id)
      ORDER BY VEC_DISTANCE_COSINE(c.embedding, @q), c.chunk_id LIMIT 5) h
JOIN articles a ON a.article_id = h.article_id AND a.revision_id = h.revision_id
ORDER BY h.score DESC, h.chunk_id;
