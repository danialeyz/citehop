-- C03 corpus schema for MariaDB 11.8 (source of truth). Safe to rerun.
-- Apply with: python -m citehop.apply_sql sql/corpus_schema.sql
-- Titles and category names use utf8mb4_bin so distinct Wikipedia names never collide
-- under the server's accent/case-insensitive default collation.

CREATE TABLE IF NOT EXISTS corpus_versions (
  version_id       INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  content_sha256   CHAR(64) CHARACTER SET ascii NOT NULL,
  source_corpus_id CHAR(64) CHARACTER SET ascii NOT NULL,
  subset           VARCHAR(16) CHARACTER SET ascii NOT NULL,
  article_count    INT UNSIGNED NOT NULL,
  category_count   INT UNSIGNED NOT NULL,
  link_count       INT UNSIGNED NOT NULL,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_versions_content (content_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS articles (
  article_id         INT UNSIGNED NOT NULL PRIMARY KEY,  -- Wikipedia page ID
  title              VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  revision_id        BIGINT UNSIGNED NOT NULL,
  revision_timestamp DATETIME NULL,                      -- UTC
  source_url         VARCHAR(1024) NOT NULL,
  revision_url       VARCHAR(1024) NOT NULL,
  text               MEDIUMTEXT NOT NULL,
  text_sha256        CHAR(64) CHARACTER SET ascii NOT NULL,
  length_chars       INT UNSIGNED NOT NULL,
  is_smoke           BOOLEAN NOT NULL DEFAULT FALSE,
  license_url        VARCHAR(255) NOT NULL,
  attribution        VARCHAR(512) NOT NULL,
  UNIQUE KEY uq_articles_title (title),
  UNIQUE KEY uq_articles_revision (article_id, revision_id),
  KEY idx_articles_length (length_chars),
  CONSTRAINT chk_articles_length CHECK (length_chars > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS article_categories (
  article_id    INT UNSIGNED NOT NULL,
  category_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (article_id, category_name),
  KEY idx_categories_name (category_name, article_id),
  CONSTRAINT fk_categories_article FOREIGN KEY (article_id)
    REFERENCES articles (article_id) ON DELETE CASCADE,
  CONSTRAINT chk_categories_name CHECK (category_name <> '')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS article_links (
  source_article_id INT UNSIGNED NOT NULL,
  target_article_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (source_article_id, target_article_id),
  KEY idx_links_target (target_article_id, source_article_id),
  CONSTRAINT fk_links_source FOREIGN KEY (source_article_id)
    REFERENCES articles (article_id) ON DELETE CASCADE,
  CONSTRAINT fk_links_target FOREIGN KEY (target_article_id)
    REFERENCES articles (article_id) ON DELETE CASCADE,
  CONSTRAINT chk_links_not_self CHECK (source_article_id <> target_article_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rows are written by C05 together with their embedding (a vector index requires NOT NULL).
-- The composite foreign key pins every chunk to its article's current revision: a revision
-- update is rejected while old chunks exist, so the loader must delete them first.
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id         CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
  article_id       INT UNSIGNED NOT NULL,
  revision_id      BIGINT UNSIGNED NOT NULL,
  chunk_config     CHAR(64) CHARACTER SET ascii NOT NULL,
  ordinal          SMALLINT UNSIGNED NOT NULL,
  char_start       INT UNSIGNED NOT NULL,
  char_end         INT UNSIGNED NOT NULL,
  token_count      SMALLINT UNSIGNED NOT NULL,
  text             TEXT NOT NULL,
  embedding        VECTOR(768) NOT NULL,
  embedding_config CHAR(64) CHARACTER SET ascii NOT NULL,
  UNIQUE KEY uq_chunks_position (article_id, revision_id, chunk_config, ordinal),
  KEY idx_chunks_config (chunk_config, embedding_config),
  FULLTEXT KEY ft_chunks_text (text),
  VECTOR INDEX vx_chunks_embedding (embedding) M=16 DISTANCE=cosine,
  CONSTRAINT fk_chunks_article_revision FOREIGN KEY (article_id, revision_id)
    REFERENCES articles (article_id, revision_id) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT chk_chunks_span CHECK (char_end > char_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- C05: full settings behind each embedding_config hash (model/tokenizer revision, library
-- versions, chunk size/overlap, input formatting, pooling, normalization). Rows are immutable.
CREATE TABLE IF NOT EXISTS embedding_configs (
  embedding_config CHAR(64) CHARACTER SET ascii NOT NULL PRIMARY KEY,
  chunk_config     CHAR(64) CHARACTER SET ascii NOT NULL,
  config_json      JSON NOT NULL,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
