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

-- Not in CITEHOP_BOOTSTRAP.md 4.9. Added in migration M2 for handoff D9 (card #34).
-- Stores a hash of the query, never the raw text. The API (card #34) computes it.
CREATE TABLE IF NOT EXISTS search_log (
  log_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  ts         TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  query_hash BINARY(32) NOT NULL,
  config     VARCHAR(8) NOT NULL,
  n_results  SMALLINT NOT NULL,
  latency_ms INT NOT NULL,
  KEY k_ts (ts)
) ENGINE=InnoDB;
