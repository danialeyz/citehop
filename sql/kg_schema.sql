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
