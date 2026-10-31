"""citehop.embed.run against a disposable MariaDB (CITEHOP_TEST_DB_NAME) with a fake model."""

import hashlib

import pytest
from corpus_fixtures import corpus, revise
from test_chunking import VERSIONS, tokenize
from test_corpus_db import db, rows  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


class FakeEmbedder:
    def __init__(self, versions=VERSIONS):
        self.versions, self.calls = versions, 0
        self.tokenize = tokenize

    def count(self, text):
        return len(tokenize(text))

    def input_length(self, text):
        return len(tokenize(text)) + 2

    def embed(self, texts):
        self.calls += 1
        out = []
        for text in texts:
            seed = hashlib.sha256(text.encode()).digest()
            vector = [seed[i % 32] / 255 + 0.01 for i in range(768)]
            norm = sum(v * v for v in vector) ** 0.5
            out.append([v / norm for v in vector])
        return out


def load(connection, snapshot, manifest):
    from citehop.corpus import load as load_corpus

    return load_corpus(connection, snapshot, manifest)


def test_run_skips_current_work_and_invalidates_changes(db):  # noqa: F811
    from citehop.embed import configs, run, status

    snapshot, manifest = corpus()
    load(db, snapshot, manifest)
    first = run(db, FakeEmbedder())
    assert (first["articles_embedded"], first["chunks_written"]) == (3, 3)
    stored = rows(db, "SELECT chunk_id, embedding_config, VEC_ToText(embedding) FROM chunks")
    assert len(stored) == 3 and all(len(r[2].strip("[]").split(",")) == 768 for r in stored)
    assert rows(db, "SELECT COUNT(*) FROM embedding_configs") == [(1,)]

    fake = FakeEmbedder()
    again = run(db, fake)
    assert (again["articles_skipped"], again["chunks_written"], fake.calls) == (3, 0, 0)
    assert rows(db, "SELECT chunk_id, embedding_config, VEC_ToText(embedding) FROM chunks") \
        == stored

    # Changed text (new revision) re-embeds only that article.
    load(db, *revise(snapshot, manifest, 3, "The perceptron was revised entirely."))
    changed = run(db, FakeEmbedder())
    assert (changed["articles_embedded"], changed["articles_skipped"]) == (1, 2)
    text = rows(db, "SELECT text FROM chunks WHERE article_id = 3")
    assert text == [("The perceptron was revised entirely.",)]

    # Changed configuration (here: torch build) cannot reuse any vector.
    newer = FakeEmbedder({**VERSIONS, "torch": "t2"})
    swapped = run(db, newer)
    assert (swapped["articles_embedded"], swapped["chunks_deleted"]) == (3, 3)
    _, embedding_config, _ = configs(newer.versions)
    assert rows(db, "SELECT DISTINCT embedding_config FROM chunks") == [(embedding_config,)]
    report = status(db, swapped["chunk_config"], embedding_config)
    assert (report["covered_articles"], report["stale_chunks"]) == (3, 0)


def test_interrupted_run_resumes_without_redoing_committed_articles(db):  # noqa: F811
    from citehop.embed import run

    load(db, *corpus())

    class Failing(FakeEmbedder):
        def embed(self, texts):
            if self.calls == 2:
                raise RuntimeError("interrupted")
            return super().embed(texts)

    with pytest.raises(RuntimeError):
        run(db, Failing())
    assert rows(db, "SELECT COUNT(DISTINCT article_id) FROM chunks") == [(2,)]
    resumed = run(db, FakeEmbedder())
    assert (resumed["articles_skipped"], resumed["articles_embedded"]) == (2, 1)
